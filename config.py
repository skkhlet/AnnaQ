"""
إعدادات مشروع عنّاق
=====================
لو بدّلنا أي شيء نغيّره هنا بس.
"""

# النموذج المستخدم للمحادثة
CHAT_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# النموذج المستخدم لتحويل الصوت
STT_MODEL = "whisper-large-v3"

# إعدادات الصوت
SAMPLE_RATE = 16000
SILENCE_THRESHOLD = 500
SILENCE_DURATION = 1.0
