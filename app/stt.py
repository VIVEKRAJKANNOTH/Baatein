"""
stt.py — Speech-to-Text via Sarvam WebSocket.
"""

import json
import websockets
from .config import SARVAM_STT_WS_URL, SARVAM_HEADERS, ts


async def connect():
    """Open a WebSocket connection to Sarvam STT. Returns the connection or None on failure."""
    try:
        ws = await websockets.connect(
            SARVAM_STT_WS_URL,
            additional_headers=SARVAM_HEADERS,
            ping_interval=20,
        )
        print(f"  [{ts()}] [STT] Connected to Sarvam STT")
        return ws
    except Exception as e:
        print(f"  [{ts()}] [STT] Connect failed: {e}")
        return None


async def send_audio(ws, audio_data: str):
    """Send an audio chunk to the STT WebSocket.

    Args:
        ws: The STT WebSocket connection.
        audio_data: Base64-encoded audio data.
    """
    message = {
        "audio": {
            "data": audio_data,
            "sample_rate": 16000,
            "encoding": "audio/wav",
        }
    }
    await ws.send(json.dumps(message))


async def listen(ws, on_transcript):
    """Listen for transcripts from the STT WebSocket.

    Calls on_transcript(text) for each transcript received.
    Raises websockets.exceptions.ConnectionClosed when disconnected.
    """
    async for raw_message in ws:
        response = json.loads(raw_message)
        transcript = response.get("data", {}).get("transcript", "")
        if transcript:
            await on_transcript(transcript)
