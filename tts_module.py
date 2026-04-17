"""
عنّاق — تحويل النص إلى صوت
==============================
Groq Orpheus للصوت، لو خلص الحد يكمل بالنص فقط.

pip install groq python-dotenv pygame
"""

import os
import tempfile
from dotenv import load_dotenv
load_dotenv()

import pygame
from groq import Groq
import base64
import tempfile


class AnnaqTTS:
    def __init__(self):
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.groq_model = "canopylabs/orpheus-arabic-saudi"
        self.groq_voice = "aisha"
        self.voice_available = True

    def get_audio_base64(self, text: str) -> str:
        """
        Generate audio from text and return as base64 string.
        Uses the same Groq Orpheus model.
        """
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            temp_path = tmp.name

        if self._generate(text, temp_path):
            with open(temp_path, 'rb') as f:
                audio_bytes = f.read()
            os.unlink(temp_path)
            return base64.b64encode(audio_bytes).decode('utf-8')
        return ""

    def _generate(self, text: str, path: str) -> bool:
        """حوّل نص إلى ملف صوتي."""
        try:
            response = self.client.audio.speech.create(
                model=self.groq_model,
                voice=self.groq_voice,
                input=text,
                response_format="wav",
            )
            response.write_to_file(path)
            return True
        except Exception as e:
            if "rate_limit" in str(e) or "429" in str(e):
                if self.voice_available:
                    print("⚠️ حد الصوت اليومي خلص — نكمل بالنص")
                    self.voice_available = False
            else:
                print(f"❌ خطأ TTS: {e}")
            return False

    def _play(self, path: str):
        """شغّل ملف WAV."""
        try:
            pygame.mixer.init()
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.wait(100)
            pygame.mixer.music.unload()
            pygame.mixer.quit()  # فكّ المايك
        except Exception as e:
            print(f"❌ خطأ تشغيل: {e}")
            try:
                pygame.mixer.quit()
            except:
                pass

    def _split_text(self, text: str, max_len: int = 190) -> list:
        if len(text) <= max_len:
            return [text]
        parts = []
        while text:
            if len(text) <= max_len:
                parts.append(text)
                break
            cut = text.rfind(".", 0, max_len)
            if cut == -1:
                cut = text.rfind("،", 0, max_len)
            if cut == -1:
                cut = text.rfind(" ", 0, max_len)
            if cut == -1:
                cut = max_len
            parts.append(text[:cut + 1].strip())
            text = text[cut + 1:].strip()
        return parts

    def speak(self, text: str):
        """حوّل النص لصوت. لو الحد خلص يتخطى بدون ما يأثر على المايك."""
        if not self.voice_available:
            return  # نكمل بالنص فقط — المحادثة ما توقف

        parts = self._split_text(text)
        for part in parts:
            if not part:
                continue
            path = os.path.join(tempfile.gettempdir(), "annaq_tts.wav")
            if self._generate(part, path):
                self._play(path)
                if os.path.exists(path):
                    os.unlink(path)
            else:
                return  # الحد خلص، وقّف الصوت بس كمّل المحادثة
            


if __name__ == "__main__":
        if not os.environ.get("GROQ_API_KEY"):
            print("❌ سوّ ملف .env واكتب فيه: GROQ_API_KEY=gsk_مفتاحك")
            exit(1)

        tts = AnnaqTTS()

        print("=" * 40)
        print("  عنّاق — تحويل النص إلى صوت")
        print("=" * 40)

        while True:
            text = input("\nاكتب نص (أو 'خروج'): ").strip()
            if text in ["خروج", "exit", "q"]:
                break
            if text:
                print("🔊 جاري التشغيل...")
                tts.speak(text)

    

 