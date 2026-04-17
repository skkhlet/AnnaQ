"""
عنّاق — محادثة بالصوت
=======================
يبدأ مباشرة بدون انتظار

pip install groq python-dotenv sounddevice numpy soundfile pygame
"""

import os
import time
import numpy as np
from dotenv import load_dotenv
load_dotenv()

import pygame
from stt_module import AnnaqSTT
from annaq_agent import AnnaqAgent
from tts_module import AnnaqTTS


def play_beep():
    """صوت بيب = دور الزائر."""
    sample_rate = 44100
    duration = 0.3
    freq = 800
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    tone = (np.sin(2 * np.pi * freq * t) * 3000).astype(np.int16)
    stereo = np.column_stack([tone, tone])

    pygame.mixer.init(frequency=sample_rate, channels=2)
    sound = pygame.sndarray.make_sound(stereo)
    sound.play()
    pygame.time.wait(int(duration * 1000))
    pygame.mixer.quit()


def main():
    if not os.environ.get("GROQ_API_KEY"):
        print("❌ سوّ ملف .env واكتب فيه: GROQ_API_KEY=gsk_مفتاحك")
        exit(1)

    stt = AnnaqSTT()
    agent = AnnaqAgent()
    tts = AnnaqTTS()

    print("=" * 40)
    print("  عنّاق — رفيقك السياحي")
    print("=" * 40)

    # عنّاق يبدأ مباشرة
    greeting = agent.chat("ابدأ المحادثة مع الزائر بتحية لطيفة واسأله وش يبي يسوي اليوم")
    print(f"\nعنّاق: {greeting}")
    tts.speak(greeting)

    while True:
        time.sleep(1.5)
        play_beep()

        text = stt.listen(threshold=1000, timeout=20)

        # ضجيج عابر
        if text is not None and not text.strip():
            continue

        # سكت 20 ثانية
        if text is None:
            prompt = agent.chat("الزائر ساكت. شجّعه بسؤال خفيف")
            print(f"\nعنّاق: {prompt}")
            tts.speak(prompt)
            continue

        # تكلم
        print(f"\nأنت: {text}")
        reply = agent.chat(text)
        print(f"\nعنّاق: {reply}")
        tts.speak(reply)

        # لو ودّع
        if any(word in reply for word in ["السلامة", "يحفظك", "نشوفك", "أمان الله"]):
            break

    print("\n👋 انتهت المحادثة")


if __name__ == "__main__":
    main()
