import {
    renderLayout,
    renderCarousel,
    renderDetails,
    renderList,
    renderInitialScreen
} from "./ui.js";

// ===== GLOBAL STATE =====
let isListeningActive = false;
let isAgentProcessing = false;
let currentRecommendations = [];
let mediaStream = null;
let audioContext = null;
let sourceNode = null;
let processorNode = null;
let silenceTimer = null;
let audioBuffer = [];
let analyserNode = null;
let sampleRate = 16000; // target sample rate for Whisper

// ===== SOCKET.IO =====
const socket = io('http://localhost:5000');

socket.on('connect', () => {
    console.log('Connected to Annaq backend');
    document.body.addEventListener('click', initAudioAndStart, { once: true });
    showToast("انقر على الشاشة لبدء المحادثة", 3000);
});

function initAudioAndStart() {
    console.log("User gesture received, starting listening...");
    startListening();
}

socket.on('agent_reply', (data) => {
    const { reply, recommendations, audio_base64 } = data;
    console.log('Agent reply:', reply);
    
    if (audio_base64 && audio_base64.length > 0) {
        playAudioBase64(audio_base64);
    } else {
        speak(reply);
    }
    
    if (recommendations && recommendations.length) {
        currentRecommendations = recommendations;
        switchToCarousel(recommendations);
    } else {
        showToast(reply);
    }
    isAgentProcessing = false;
    startListening();
});

socket.on('feedback_ack', (data) => {
    console.log('Feedback acknowledged', data);
    showToast('شكراً لك! تم تسجيل اختيارك.');
    startListening();
});

socket.on('transcription_result', (data) => {
    if (data.text && !isAgentProcessing) {
        stopListening();
        isAgentProcessing = true;
        socket.emit('user_message', { message: data.text });
        showToast("جاري المعالجة...", 1000);
    }
});

// ===== UI Helpers =====
function showToast(message, duration = 3000) {
    const toast = document.createElement('div');
    toast.textContent = message;
    toast.style.position = 'fixed';
    toast.style.bottom = '120px';
    toast.style.left = '50%';
    toast.style.transform = 'translateX(-50%)';
    toast.style.background = '#ff7849';
    toast.style.color = 'white';
    toast.style.padding = '12px 24px';
    toast.style.borderRadius = '30px';
    toast.style.zIndex = 1000;
    toast.style.fontSize = '18px';
    document.body.appendChild(toast);
    if (duration > 0) {
        setTimeout(() => toast.remove(), duration);
    }
}

function setMicColor(listening) {
    const indicator = document.getElementById('micIndicator');
    if (!indicator) return;
    if (listening) {
        indicator.classList.remove('grey');
    } else {
        indicator.classList.add('grey');
    }
}

// ===== WAV RECORDER =====
function encodeWAV(samples, sampleRate) {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);
    
    // RIFF chunk
    writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + samples.length * 2, true);
    writeString(view, 8, 'WAVE');
    writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeString(view, 36, 'data');
    view.setUint32(40, samples.length * 2, true);
    
    // Write PCM samples
    let offset = 44;
    for (let i = 0; i < samples.length; i++) {
        let s = Math.max(-1, Math.min(1, samples[i]));
        view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
        offset += 2;
    }
    return buffer;
}

function writeString(view, offset, str) {
    for (let i = 0; i < str.length; i++) {
        view.setUint8(offset + i, str.charCodeAt(i));
    }
}

function resample(samples, origSampleRate, targetSampleRate) {
    if (origSampleRate === targetSampleRate) return samples;
    const ratio = origSampleRate / targetSampleRate;
    const newLength = Math.round(samples.length / ratio);
    const result = new Float32Array(newLength);
    for (let i = 0; i < newLength; i++) {
        const srcIndex = i * ratio;
        const lowIndex = Math.floor(srcIndex);
        const highIndex = Math.min(lowIndex + 1, samples.length - 1);
        const frac = srcIndex - lowIndex;
        result[i] = samples[lowIndex] * (1 - frac) + samples[highIndex] * frac;
    }
    return result;
}

// ===== AUDIO RECORDING WITH VAD =====
async function startListening() {
    if (isAgentProcessing) {
        console.log("Cannot start listening: agent is processing");
        return;
    }
    if (isListeningActive) return;

    try {
        mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        if (audioContext.state === 'suspended') {
            await audioContext.resume();
        }
        
        sampleRate = audioContext.sampleRate; // actual device sample rate
        
        sourceNode = audioContext.createMediaStreamSource(mediaStream);
        analyserNode = audioContext.createAnalyser();
        analyserNode.fftSize = 256;
        
        // ScriptProcessorNode for raw PCM capture
        processorNode = audioContext.createScriptProcessor(4096, 1, 1);
        
        audioBuffer = [];
        
        processorNode.onaudioprocess = (event) => {
            if (!isListeningActive) return;
            const inputData = event.inputBuffer.getChannelData(0);
            // Copy samples
            const copy = new Float32Array(inputData.length);
            copy.set(inputData);
            audioBuffer.push(copy);
        };
        
        sourceNode.connect(analyserNode);
        sourceNode.connect(processorNode);
        processorNode.connect(audioContext.destination);
        
        isListeningActive = true;
        setMicColor(true);
        console.log("Recording started (WAV)");
        
        // VAD using analyser
        const dataArray = new Uint8Array(analyserNode.frequencyBinCount);
        
        const checkVolume = () => {
            if (!isListeningActive || !analyserNode) return;
            
            analyserNode.getByteFrequencyData(dataArray);
            let avg = 0;
            for (let i = 0; i < dataArray.length; i++) {
                avg += dataArray[i];
            }
            avg = avg / dataArray.length;
            
            const isSpeaking = avg > 12;
            
            if (isSpeaking) {
                if (silenceTimer) clearTimeout(silenceTimer);
                silenceTimer = null;
            } else if (!silenceTimer && isListeningActive) {
                silenceTimer = setTimeout(() => {
                    if (isListeningActive) {
                        console.log("Silence detected, stopping recording");
                        stopListening();
                    }
                }, 800);
            }
            
            requestAnimationFrame(checkVolume);
        };
        
        checkVolume();
        
    } catch (err) {
        console.error("Microphone error:", err);
        showToast("الرجاء السماح بالوصول إلى الميكروفون.", 3000);
        isListeningActive = false;
        setMicColor(false);
    }
}

function stopListening() {
    if (silenceTimer) {
        clearTimeout(silenceTimer);
        silenceTimer = null;
    }
    
    if (isListeningActive) {
        isListeningActive = false;
        setMicColor(false);
        console.log("Recording stopped, processing audio...");
        
        // Combine all buffers
        let totalLength = 0;
        for (let buf of audioBuffer) {
            totalLength += buf.length;
        }
        const combined = new Float32Array(totalLength);
        let offset = 0;
        for (let buf of audioBuffer) {
            combined.set(buf, offset);
            offset += buf.length;
        }
        
        // Resample to 16000 Hz (Whisper expects 16kHz)
        const targetRate = 16000;
        let samples = combined;
        if (sampleRate !== targetRate) {
            samples = resample(combined, sampleRate, targetRate);
        }
        
        // Encode as WAV
        const wavBuffer = encodeWAV(samples, targetRate);
        const blob = new Blob([wavBuffer], { type: 'audio/wav' });
        
        // Convert to base64 and send
        const reader = new FileReader();
        reader.readAsDataURL(blob);
        reader.onloadend = () => {
            const base64Audio = reader.result.split(',')[1];
            socket.emit('audio_stream', { audio: base64Audio });
        };
        
        // Cleanup
        if (processorNode) {
            processorNode.disconnect();
            processorNode = null;
        }
        if (sourceNode) {
            sourceNode.disconnect();
            sourceNode = null;
        }
        if (analyserNode) {
            analyserNode.disconnect();
            analyserNode = null;
        }
        if (audioContext) {
            audioContext.close().catch(e => console.warn);
            audioContext = null;
        }
        if (mediaStream) {
            mediaStream.getTracks().forEach(track => track.stop());
            mediaStream = null;
        }
        audioBuffer = [];
    }
}

// ===== AUDIO PLAYBACK =====
function playAudioBase64(base64String) {
    if (!base64String || base64String.length === 0) return;
    const base64Data = base64String.includes('base64,')
        ? base64String.split('base64,')[1]
        : base64String;
    const binaryString = atob(base64Data);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }
    const blob = new Blob([bytes], { type: 'audio/wav' });
    const audioUrl = URL.createObjectURL(blob);
    const audio = new Audio(audioUrl);
    audio.play().catch(e => console.warn("Audio play failed:", e));
    audio.onended = () => URL.revokeObjectURL(audioUrl);
}

function speak(text) {
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'ar-SA';
    utterance.rate = 0.9;
    window.speechSynthesis.speak(utterance);
}

// ===== VIEW MANAGEMENT =====
function switchToCarousel(recommendations) {
    renderLayout();
    renderCarousel(recommendations);
    attachCarouselEvents();
}

function attachCarouselEvents() {
    const cards = document.querySelectorAll('.card');
    cards.forEach(card => {
        card.addEventListener('click', (e) => {
            e.stopPropagation();
            const isActive = card.classList.contains('active');
            if (isActive) {
                const placeId = card.dataset.id;
                socket.emit('feedback', { place_id: placeId });
                showToast('شكراً! تم تسجيل اختيارك.');
                isAgentProcessing = false;
                startListening();
            } else {
                focusCard(card);
            }
        });
    });
}

function focusCard(card) {
    const carousel = document.getElementById("carousel");
    if (!carousel) return;
    const carouselRect = carousel.getBoundingClientRect();
    const cardRect = card.getBoundingClientRect();
    const scrollOffset = cardRect.left - carouselRect.left - carousel.offsetWidth / 2 + cardRect.width / 2;
    carousel.scrollBy({ left: scrollOffset, behavior: "smooth" });
}

function resetToInitial() {
    stopListening();
    socket.emit('reset', {});
    renderInitialScreen();
    isAgentProcessing = false;
    currentRecommendations = [];
    setTimeout(() => startListening(), 500);
}

window.resetToInitial = resetToInitial;

function requestFullscreen() {
    const el = document.documentElement;
    if (el.requestFullscreen) {
        el.requestFullscreen().catch(() => console.log("Fullscreen denied"));
    }
}

function init() {
    console.log("Annaq is starting...");
    requestFullscreen();
    renderLayout();
    renderInitialScreen();
    // Wait for user click (handled by socket connect)
}

init();