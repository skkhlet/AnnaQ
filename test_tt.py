# test_tts.py
from tts_module import AnnaqTTS
import base64

tts = AnnaqTTS()
audio_b64 = tts.get_audio_base64("مرحبا، هذا اختبار للصوت")
print(f"Audio base64 length: {len(audio_b64)}")
if len(audio_b64) > 100:
    # Decode and save to file to test manually
    with open("test_output.wav", "wb") as f:
        f.write(base64.b64decode(audio_b64))
    print("Saved test_output.wav – play it to verify voice quality")
else:
    print("TTS failed – check API key and rate limits")