
"pip install flask flask-socketio "
"pip install aiohttp python-socketio[asyncio]"


import os
import base64
import io
from aiohttp import web
import socketio
import asyncio
from dotenv import load_dotenv
load_dotenv()  # Load API key from .env

from annaq_agent import AnnaqAgent
from tts_module import AnnaqTTS
from groq import Groq

# Create Socket.IO server
sio = socketio.AsyncServer(cors_allowed_origins='*', async_mode='aiohttp')
app = web.Application()
sio.attach(app)

# Create agent and TTS
agent = AnnaqAgent()
tts = AnnaqTTS()

# ========== SPEECH-TO-TEXT ==========
def transcribe_audio(audio_bytes: bytes) -> str:
    """Send audio bytes to Groq Whisper and return transcribed text."""
    client = Groq()
    with io.BytesIO(audio_bytes) as file:
        file.name = "temp_audio.wav"
        transcription = client.audio.transcriptions.create(
            file=file,
            model="whisper-large-v3",
            language="ar",
            response_format="text"
        )
    return transcription.strip()

@sio.event
async def audio_stream(sid, data):
    """Receive audio from frontend, transcribe, and return text."""
    try:
        audio_bytes = base64.b64decode(data['audio'])
        transcription = await asyncio.to_thread(transcribe_audio, audio_bytes)
        await sio.emit('transcription_result', {'text': transcription}, room=sid)
    except Exception as e:
        print(f"Transcription error: {e}")
        await sio.emit('transcription_result', {'text': '', 'error': str(e)}, room=sid)

# ========== MAIN CHAT HANDLER ==========
@sio.event
async def user_message(sid, data):
    message = data.get('message', '')
    print(f'Message from {sid}: {message}')

    # Get agent reply
    reply = await asyncio.to_thread(agent.chat, message)

    # Get recommendations if any
    recs = []
    if hasattr(agent, 'get_last_recommendations'):
        recs = agent.get_last_recommendations()

    # Generate audio for the reply
    audio_b64 = await asyncio.to_thread(tts.get_audio_base64, reply)

    await sio.emit('agent_reply', {
        'reply': reply,
        'recommendations': recs,
        'audio_base64': audio_b64
    }, room=sid)

# ========== FEEDBACK ==========
@sio.event
async def feedback(sid, data):
    place_id = data.get('place_id')
    print(f'Feedback from {sid}: liked {place_id}')

    if hasattr(agent, 'give_feedback'):
        await asyncio.to_thread(agent.give_feedback, place_id)
        await sio.emit('feedback_ack', {'status': 'ok', 'place_id': place_id}, room=sid)
    else:
        await sio.emit('feedback_ack', {'status': 'error', 'message': 'Feedback method not available'}, room=sid)

# ========== RESET ==========
@sio.event
async def reset(sid, data):
    print(f'Reset requested from {sid}')
    agent.reset()
    await sio.emit('reset_ack', {'status': 'ok'}, room=sid)

# ========== CONNECTION EVENTS ==========
@sio.event
async def connect(sid, environ):
    print(f'Client {sid} connected')
    await sio.emit('connected', {'data': 'Connected to Annaq backend'}, room=sid)

@sio.event
async def disconnect(sid):
    print(f'Client {sid} disconnected')

# ========== STATIC FILES ==========
async def serve_index(request):
    return web.FileResponse('index.html')

async def serve_static(request):
    path = request.match_info['path']
    return web.FileResponse(path)

app.router.add_get('/', serve_index)
app.router.add_get('/{path:.*}', serve_static)

# ========== RUN SERVER ==========
if __name__ == '__main__':
    web.run_app(app, host='0.0.0.0', port=5000)