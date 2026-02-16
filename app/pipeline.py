"""
pipeline.py — Orchestrates LLM → Search? → TTS streaming.

This is the "brain" of the voice agent. It:
1. Takes a user transcript
2. Starts a speculative web search in parallel
3. Streams LLM tokens, detects [SEARCH:] commands
4. If search → uses pre-fetched results → second LLM → TTS
5. If no search → streams sentences directly to TTS

All TTS happens concurrently with LLM via asyncio.Queue.
"""

import re
import json
import time
import asyncio

from . import llm, tts
from .config import (
    http_client, SARVAM_API_KEY, SARVAM_CHAT_URL, SENTENCE_END,
    conversation_history, sanitize_history, ts
)
from .search import web_search, clean_for_search, query_similarity


async def run(websocket, transcript: str, cancel_event: asyncio.Event):
    """
    Main pipeline: transcript → LLM → TTS, with search support.

    This is the entry point called by the server for each user utterance.
    """
    sanitize_history()
    conversation_history.append({"role": "user", "content": transcript})

    await websocket.send_text(json.dumps({"type": "tts_start"}))
    t0 = time.time()
    print(f"\n  [{ts()}] [PIPELINE] LLM call started <- \"{transcript}\"")

    # ─── Shared state ───
    sentences_queue = asyncio.Queue()
    sentence_buffer = ""
    full_response = ""
    first_token = True
    is_search = False
    search_detected = asyncio.Event()

    # ─── LLM Producer: stream tokens, detect search, feed sentences ───
    async def llm_producer():
        nonlocal full_response, first_token, sentence_buffer, is_search

        try:
            async for content in llm.stream_tokens(conversation_history, cancel_event):
                if first_token:
                    print(f"  [{ts()}] [LLM] First token (+{time.time()-t0:.2f}s)")
                    first_token = False

                full_response += content
                await websocket.send_text(json.dumps({"type": "llm_chunk", "text": content}))

                # Check for [SEARCH:] in first ~80 chars
                if not search_detected.is_set():
                    if "[SEARCH:" in full_response:
                        is_search = True
                        search_detected.set()
                        print(f"  [{ts()}] [SEARCH] Detected!")
                        continue
                    elif len(full_response) > 80 or SENTENCE_END.search(full_response):
                        is_search = False
                        sentence_buffer = full_response
                        sentence_buffer = llm.extract_sentences(sentence_buffer, sentences_queue)
                        search_detected.set()
                        print(f"  [{ts()}] [LLM] Normal response, starting TTS stream...")
                        continue

                # Buffer for TTS if NOT a search response
                if search_detected.is_set() and not is_search:
                    sentence_buffer += content
                    sentence_buffer = llm.extract_sentences(sentence_buffer, sentences_queue)
        finally:
            # Push remaining buffer
            if not is_search and sentence_buffer.strip():
                clean = llm.clean_for_tts(sentence_buffer.strip())
                if clean:
                    print(f"  [{ts()}] [LLM] Final fragment -> TTS: \"{clean[:60]}\"")
                    sentences_queue.put_nowait(clean)
            sentences_queue.put_nowait(None)  # Signal done
            if not search_detected.is_set():
                search_detected.set()

    # ─── TTS Consumer: waits for search detection, then streams audio ───
    async def tts_consumer():
        await search_detected.wait()

        if is_search or cancel_event.is_set():
            return  # Search path handles TTS separately

        chunk_count = await tts.stream_to_client(websocket, sentences_queue, cancel_event)
        if chunk_count > 0:
            print(f"  [{ts()}] [TTS] First audio! (+{time.time()-t0:.2f}s from start)")

    # ─── Start speculative search + LLM + TTS concurrently ───
    clean_query = clean_for_search(transcript)
    speculative_search_task = asyncio.create_task(
        asyncio.to_thread(web_search, clean_query)
    )
    print(f"  [{ts()}] [SEARCH] Speculative: \"{clean_query[:60]}\"")

    await asyncio.gather(llm_producer(), tts_consumer())

    if cancel_event.is_set():
        speculative_search_task.cancel()
        conversation_history.pop()
        return

    t_llm = time.time() - t0
    print(f"  [{ts()}] [LLM] Done in {t_llm:.2f}s: \"{full_response[:80]}\"")

    # ─── Handle search if detected ───
    if is_search:
        search_match = re.search(r'\[SEARCH:\s*(.+?)\]', full_response)
        if search_match:
            search_query = search_match.group(1).strip()

            await websocket.send_text(json.dumps({
                "type": "llm_chunk",
                "text": "\n\nSearching the web...\n"
            }))
            await websocket.send_text(json.dumps({"type": "search_start"}))

            # Get search results — use speculative if query is similar enough
            t_search = time.time()
            similarity = query_similarity(clean_query, search_query)
            print(f"  [{ts()}] [SEARCH] Query similarity: {similarity:.0%} "
                  f"(clean=\"{clean_query[:40]}\" vs llm=\"{search_query[:40]}\")")

            if similarity >= 0.4:
                try:
                    search_results = await asyncio.wait_for(speculative_search_task, timeout=5.0)
                    print(f"  [{ts()}] [SEARCH] Using speculative results (waited {time.time()-t_search:.2f}s)")
                except (asyncio.TimeoutError, Exception) as e:
                    print(f"  [{ts()}] [SEARCH] Speculative failed ({e}), fresh search...")
                    search_results = await asyncio.to_thread(web_search, search_query)
                    print(f"  [{ts()}] [SEARCH] Fresh search done in {time.time()-t_search:.2f}s")
            else:
                speculative_search_task.cancel()
                print(f"  [{ts()}] [SEARCH] Query too different, using LLM's refined query...")
                search_results = await asyncio.to_thread(web_search, search_query)
                print(f"  [{ts()}] [SEARCH] Refined search done in {time.time()-t_search:.2f}s")

            # Quick spoken cue (removed)
            # await tts.speak_short(websocket, "Here's what I found.", cancel_event)

            if cancel_event.is_set():
                conversation_history.pop()
                return

            await websocket.send_text(json.dumps({"type": "search_audio_done"}))

            # Second LLM → TTS with search results
            conversation_history.append({"role": "assistant", "content": full_response})
            conversation_history.append({
                "role": "user",
                "content": f"Here are the web search results for '{search_query}':\n\n"
                           f"{search_results}\n\n"
                           f"Synthesize a comprehensive and natural answer for speaking aloud. "
                           f"Do NOT say 'Here is what I found'. Just give the detailed answer."
            })

            await websocket.send_text(json.dumps({"type": "llm_chunk", "text": "\n\n"}))
            await asyncio.sleep(0.7)  # Wait for client MSE reinit
            await websocket.send_text(json.dumps({"type": "tts_start"}))

            full_response = await _search_llm_tts(websocket, cancel_event, t0)

            conversation_history.pop()  # search prompt
            conversation_history.pop()  # [SEARCH:] response

            if cancel_event.is_set():
                conversation_history.pop()
                return
    else:
        speculative_search_task.cancel()

    # ─── Finish up ───
    await websocket.send_text(json.dumps({"type": "llm_done"}))

    if cancel_event.is_set():
        conversation_history.pop()
        return

    if not full_response:
        print(f"  [{ts()}] [PIPELINE] No speakable text")
        conversation_history.pop()
        return

    # Save to history and send completion
    conversation_history.append({"role": "assistant", "content": full_response})
    total_time = time.time() - t0
    print(f"  [{ts()}] [PIPELINE] Done: Total={total_time:.2f}s")

    await websocket.send_text(json.dumps({
        "type": "tts_done",
        "total_time": round(total_time, 2),
    }))


async def _search_llm_tts(websocket, cancel_event: asyncio.Event, t0: float) -> str:
    """Run second LLM→TTS for search result summaries. Same concurrent pattern."""

    sentences_queue = asyncio.Queue()
    full_response = ""
    sentence_buffer = ""
    first_token = True

    async def llm_producer():
        nonlocal full_response, sentence_buffer, first_token

        try:
            async for content in llm.stream_tokens(conversation_history, cancel_event):
                if first_token:
                    print(f"  [{ts()}] [LLM] Search LLM token (+{time.time()-t0:.2f}s)")
                    first_token = False

                full_response += content
                await websocket.send_text(json.dumps({"type": "llm_chunk", "text": content}))
                sentence_buffer += content
                sentence_buffer = llm.extract_sentences(sentence_buffer, sentences_queue)
        finally:
            if sentence_buffer.strip():
                clean = llm.clean_for_tts(sentence_buffer.strip())
                if clean:
                    print(f"  [{ts()}] [LLM] Final fragment -> TTS: \"{clean[:60]}\"")
                    sentences_queue.put_nowait(clean)
            sentences_queue.put_nowait(None)

    async def tts_consumer():
        count = await tts.stream_to_client(websocket, sentences_queue, cancel_event)
        if count > 0:
            print(f"  [{ts()}] [TTS] First audio! (+{time.time()-t0:.2f}s from start)")

    await asyncio.gather(llm_producer(), tts_consumer())
    return full_response
