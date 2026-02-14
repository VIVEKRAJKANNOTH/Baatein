


Mic Input (Browser)
    ↓ (WebSocket stream - Audio)
Python Backend (FastAPI + WebSocket)
    ↓ (WebSocket stream - Audio)
Streaming STT
    ↓ (Text)
LLM (with Search Tool)
    ↓ (Text)
Streaming TTS
    ↓ (Audio)
Audio Stream back to client (WebSocket stream - Audio)