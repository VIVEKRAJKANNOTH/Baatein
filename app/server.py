"""
server.py — FastAPI + WebSocket endpoint.

This is the entry point. It:
1. Serves the client HTML at /
2. Handles the WebSocket at /ws
3. Manages STT connection + listener
4. Handles barge-in (cancel current response)
5. Triggers the pipeline on VAD silence

Run: python -m app.server
"""

import json
import asyncio
import websockets
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from . import stt, pipeline
from .config import ts

app = FastAPI()

# Serve React frontend
CLIENT_DIST = Path(__file__).parent.parent / "ui/dist"
CLIENT_HTML = CLIENT_DIST / "index.html"


@app.get("/")
async def get_client():
    if CLIENT_HTML.exists():
        return HTMLResponse(CLIENT_HTML.read_text())
    return HTMLResponse("<h1>Building UI... please wait</h1>")

# Mount assets
if (CLIENT_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(CLIENT_DIST / "assets")), name="assets")


@app.get("/favicon.ico")
async def favicon():
    return HTMLResponse("")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("[SERVER] Browser connected")

    # ─── Per-session state ───
    cancel_event = asyncio.Event()
    current_task = None
    ai_speaking = False
    current_utterance = []
    browser_alive = True

    stt_state = {"ws": None, "connected": False}

    # ─── STT connection ───
    async def connect_stt():
        ws = await stt.connect()
        if ws:
            stt_state["ws"] = ws
            stt_state["connected"] = True
        return ws

    # ─── Run pipeline as cancellable task ───
    async def do_llm_tts(transcript):
        nonlocal cancel_event, current_task, ai_speaking

        # Cancel any running task first
        if current_task and not current_task.done():
            cancel_event.set()
            try:
                await asyncio.wait_for(current_task, timeout=3.0)
            except asyncio.TimeoutError:
                print(f"  [{ts()}] [SERVER] Old task didn't finish, force cancelling")
                current_task.cancel()
                try:
                    await current_task
                except (asyncio.CancelledError, Exception):
                    pass
            except Exception:
                pass

        cancel_event = asyncio.Event()
        ai_speaking = True

        async def run():
            nonlocal ai_speaking
            try:
                await pipeline.run(websocket, transcript, cancel_event)
            except asyncio.CancelledError:
                print(f"  [{ts()}] [SERVER] Task cancelled")
            except Exception as e:
                print(f"  [{ts()}] [SERVER] Pipeline error: {e}")
                import traceback
                traceback.print_exc()
            finally:
                ai_speaking = False

        current_task = asyncio.create_task(run())

    # ─── Task 1: Handle messages from browser ───
    async def browser_handler():
        nonlocal browser_alive, current_utterance, ai_speaking

        try:
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)

                if message["type"] == "audio_chunk":
                    # Forward audio to STT
                    if stt_state["connected"] and stt_state["ws"]:
                        try:
                            await stt.send_audio(stt_state["ws"], message["data"])
                        except Exception:
                            stt_state["connected"] = False

                elif message["type"] == "user_stopped_speaking":
                    # VAD detected silence — trigger LLM
                    transcript = " ".join(current_utterance).strip()
                    current_utterance = []

                    if transcript:
                        print(f"  [{ts()}] [VAD] Silence -> LLM <- \"{transcript}\"")
                        await websocket.send_text(json.dumps({
                            "type": "final_transcript", "text": transcript
                        }))
                        await do_llm_tts(transcript)
                    else:
                        print(f"  [{ts()}] [VAD] Silence but no transcript, ignoring")

                elif message["type"] == "barge_in":
                    # User interrupted AI — cancel current response
                    if ai_speaking and cancel_event and not cancel_event.is_set():
                        print(f"  [{ts()}] [BARGE-IN] Cancelling AI response")
                        cancel_event.set()
                        ai_speaking = False
                        await websocket.send_text(json.dumps({"type": "stop_audio"}))

        except WebSocketDisconnect:
            print("  Browser disconnected")
            browser_alive = False

    # ─── Task 2: STT listener with auto-reconnect ───
    async def stt_listener():
        nonlocal current_utterance

        while browser_alive:
            stt_ws = await connect_stt()
            if not stt_ws:
                await asyncio.sleep(1)
                continue

            try:
                async def on_transcript(text):
                    current_utterance.append(text)
                    print(f"  [{ts()}] [STT] \"{text}\"")
                    await websocket.send_text(json.dumps({
                        "type": "transcript", "text": text
                    }))

                await stt.listen(stt_ws, on_transcript)

            except websockets.exceptions.ConnectionClosed:
                print(f"  [{ts()}] [STT] Disconnected, reconnecting...")
                stt_state["connected"] = False
            except Exception as e:
                print(f"  [{ts()}] [STT] Error: {e}, reconnecting...")
                stt_state["connected"] = False

            if browser_alive:
                await asyncio.sleep(0.5)

    # ─── Task 3: Keep-Alive Heartbeat ───
    async def keep_alive():
        while browser_alive:
            try:
                await asyncio.sleep(15)
                await websocket.send_text(json.dumps({"type": "ping"}))
            except Exception:
                pass

    # ─── Run both tasks concurrently ───
    try:
        await asyncio.gather(
            browser_handler(),
            stt_listener(),
            keep_alive(),
        )
    except Exception as e:
        print(f"  [{ts()}] [SERVER] Session error: {e}")
    finally:
        if stt_state["ws"]:
            try:
                await stt_state["ws"].close()
            except Exception:
                pass
        print("[SERVER] Session ended")


if __name__ == "__main__":
    print("Baatein Voice Agent")
    print("  STT: Sarvam saaras:v3 | LLM: sarvam-m | TTS: bulbul:v3")
    print("  Search: DuckDuckGo (speculative) | VAD: Client-side")
    print("  Barge-in: Enabled | Streaming: Sentence-level LLM->TTS")
    print("  Open http://localhost:8000")
    print("  Press Ctrl+C to stop\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
