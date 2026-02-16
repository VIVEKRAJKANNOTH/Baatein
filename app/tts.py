"""
tts.py — Text-to-Speech streaming via Sarvam WebSocket.
"""

import json
import asyncio
from sarvamai import AudioOutput, EventResponse
from .config import tts_client, ts


async def stream_to_client(websocket, sentences_queue: asyncio.Queue, cancel_event: asyncio.Event):
    """Read sentences from queue, convert to speech, stream audio chunks to browser.

    Args:
        websocket: The browser WebSocket to send audio chunks to.
        sentences_queue: Queue of sentences to speak (None = stop signal).
        cancel_event: Set this to cancel mid-stream (barge-in).

    Returns:
        Number of audio chunks sent.
    """
    chunk_count = 0

    try:
        async with tts_client.text_to_speech_streaming.connect(
            model="bulbul:v3",
            send_completion_event=True,
        ) as tts_ws:
            await tts_ws.configure(
                target_language_code="en-IN",
                speaker="shubh",
            )

            # Feeder: pull sentences from queue → convert()
            async def feeder():
                while True:
                    if cancel_event.is_set():
                        try:
                            await tts_ws.flush()
                        except Exception:
                            pass
                        break
                    try:
                        sentence = await asyncio.wait_for(sentences_queue.get(), timeout=0.5)
                    except asyncio.TimeoutError:
                        continue  # re-check cancel_event
                    if sentence is None:
                        try:
                            await tts_ws.flush()
                        except Exception:
                            pass
                        break
                    if cancel_event.is_set():
                        try:
                            await tts_ws.flush()
                        except Exception:
                            pass
                        break
                    await tts_ws.convert(sentence + " ")

            feeder_task = asyncio.create_task(feeder())

            # Reader: receive audio chunks → send to client
            async for message in tts_ws:
                if cancel_event.is_set():
                    print(f"  [{ts()}] [TTS] Cancelled (barge-in)")
                    break
                if isinstance(message, AudioOutput):
                    chunk_count += 1
                    await websocket.send_text(json.dumps({
                        "type": "audio_chunk",
                        "audio": message.data.audio,
                        "chunk_num": chunk_count,
                    }))
                elif isinstance(message, EventResponse):
                    if message.data.event_type == "final":
                        break

            await feeder_task
    except Exception as e:
        print(f"  [{ts()}] [TTS] Error: {e}")

    return chunk_count


async def speak_short(websocket, text: str, cancel_event: asyncio.Event):
    """Speak a short text cue (e.g. "Here's what I found.").

    Returns the number of audio chunks sent.
    """
    chunk_count = 0

    try:
        async with tts_client.text_to_speech_streaming.connect(
            model="bulbul:v3", send_completion_event=True,
        ) as tts_ws:
            await tts_ws.configure(target_language_code="en-IN", speaker="shubh")
            await tts_ws.convert(text)
            await tts_ws.flush()

            async for msg in tts_ws:
                if cancel_event.is_set():
                    break
                if isinstance(msg, AudioOutput):
                    chunk_count += 1
                    await websocket.send_text(json.dumps({
                        "type": "audio_chunk", "audio": msg.data.audio, "chunk_num": chunk_count,
                    }))
                elif isinstance(msg, EventResponse) and msg.data.event_type == "final":
                    break
    except Exception as e:
        print(f"  [{ts()}] [TTS] Speak error: {e}")

    return chunk_count
