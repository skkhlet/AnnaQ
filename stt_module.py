"""
عنّاق — تحويل الصوت إلى نص
============================
pip install groq python-dotenv sounddevice numpy soundfile
"""

import os
import tempfile
from collections import deque
from dotenv import load_dotenv
load_dotenv()

import numpy as np
import sounddevice as sd
import soundfile as sf
from groq import Groq


class AnnaqSTT:
    def __init__(self):
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.sample_rate = 16000

    def record(self, threshold=800, timeout=20):
        """
        سجّل من المايك.
        threshold: حد الصوت (ارفعه لو فيه ضجيج)
        timeout: كم ثانية ينتظر قبل ما يعتبر ما أحد موجود
        """
        print("🎤 تكلم...")

        pre_buffer = deque(maxlen=30)
        chunks = []
        started = False
        silent = 0
        loud_streak = 0
        required_streak = 6  # 6 مرات متتالية = كلام حقيقي مو ضجيج
        stop_after = int(1.5 * self.sample_rate / 512)
        waited = 0

        def callback(data, frames, time, status):
            nonlocal started, silent, loud_streak
            vol = np.abs(data).mean() * 1000

            if vol > threshold:
                loud_streak += 1
                if not started and loud_streak >= required_streak:
                    # كلام حقيقي مستمر — ابدأ التسجيل
                    chunks.extend(list(pre_buffer))
                    started = True
                if started:
                    silent = 0
                    chunks.append(data.copy())
            else:
                loud_streak = 0
                if started:
                    silent += 1
                    chunks.append(data.copy())
                else:
                    pre_buffer.append(data.copy())

        with sd.InputStream(samplerate=self.sample_rate, channels=1,
                            dtype="int16", blocksize=512, callback=callback):
            while not (started and silent >= stop_after):
                sd.sleep(30)
                if not started:
                    waited += 0.03
                    if waited >= timeout:
                        return None

        if not chunks:
            return None

        audio = np.concatenate(chunks)

        # تحقق إن فيه كلام فعلي
        speech_duration = len(audio) / self.sample_rate
        speech_energy = np.abs(audio).mean()

        if speech_duration < 0.8:
            return None  # قصير جداً = ضجيج

        if speech_energy < 500:
            return None  # صوت ضعيف = مو كلام حقيقي

        # أضف صمت عشان Whisper ما يقص حروف
        audio = audio.flatten()
        silence_start = np.zeros(int(0.8 * self.sample_rate), dtype=np.int16)
        silence_end = np.zeros(int(0.3 * self.sample_rate), dtype=np.int16)
        audio = np.concatenate([silence_start, audio, silence_end])

        path = os.path.join(tempfile.gettempdir(), "annaq.flac")
        sf.write(path, audio, self.sample_rate, format="FLAC")
        return path

    def transcribe(self, path):
        """حوّل ملف صوتي إلى نص."""
        with open(path, "rb") as f:
            result = self.client.audio.transcriptions.create(
                file=(os.path.basename(path), f.read()),
                model="whisper-large-v3",
                language="ar",
                temperature=0.0,
                response_format="text",
            )
        return result.strip()

    def listen(self, threshold=800, timeout=20):
        """
        سجّل وحوّل.
        threshold: حد الصوت
        timeout: مهلة الانتظار بالثواني
        """
        path = self.record(threshold=threshold, timeout=timeout)
        if path is None:
            return None
        print("⚡ جاري التحويل...")
        text = self.transcribe(path)
        os.unlink(path)
        return text


if __name__ == "__main__":
    if not os.environ.get("GROQ_API_KEY"):
        print("❌ سوّ ملف .env واكتب فيه: GROQ_API_KEY=gsk_مفتاحك")
        exit(1)

    stt = AnnaqSTT()

    print("=" * 40)
    print("  🎤 عنّاق — تحويل الصوت إلى نص")
    print("=" * 40)

    while True:
        print("\nاضغط Enter وتكلم (أو اكتب خروج)...")
        if input().strip() in ["خروج", "exit", "q"]:
            break
        text = stt.listen()
        if text is None:
            print("📝 ما سمعت شيء")
        else:
            print(f"📝 {text}")
