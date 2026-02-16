"""
llm.py — LLM streaming via Sarvam API (HTTP SSE).
"""

import json
import asyncio
from .config import http_client, SARVAM_CHAT_URL, SARVAM_API_KEY, SENTENCE_END, EMOJI_PATTERN, ts


def clean_for_tts(text: str) -> str:
    """Strip emojis and markdown artifacts from text before sending to TTS."""
    text = EMOJI_PATTERN.sub('', text)
    text = text.replace('*', '').replace('#', '').replace('`', '')
    return text.strip()


def extract_sentences(buffer: str, queue: asyncio.Queue) -> str:
    """Extract complete sentences from buffer, push them to queue.

    Returns the remaining (incomplete) buffer.
    """
    while True:
        match = SENTENCE_END.search(buffer)
        if not match:
            break
        end_pos = match.end()
        sentence = buffer[:end_pos].strip()
        buffer = buffer[end_pos:]
        clean = clean_for_tts(sentence)
        if clean:
            print(f"  [{ts()}] [LLM] Sentence -> TTS: \"{clean[:60]}\"")
            queue.put_nowait(clean)
    return buffer


async def stream_tokens(messages: list, cancel_event: asyncio.Event):
    """Stream LLM tokens from Sarvam API.

    Yields (content_str) for each token received.
    Stops if cancel_event is set.
    """
    try:
        async with http_client.stream(
            "POST", SARVAM_CHAT_URL,
            headers={"Api-Subscription-Key": SARVAM_API_KEY, "Content-Type": "application/json"},
            json={"model": "sarvam-m", "messages": messages, "stream": True},
        ) as response:
            print(f"  [{ts()}] [LLM] HTTP {response.status_code}")

            if response.status_code != 200:
                error_body = await response.aread()
                print(f"  [{ts()}] [LLM] API error: {error_body[:500]}")
                return

            async for line in response.aiter_lines():
                if cancel_event.is_set():
                    print(f"  [{ts()}] [LLM] Cancelled (barge-in)")
                    break
                if not line.startswith("data: "):
                    continue
                if line == "data: [DONE]":
                    break
                try:
                    chunk = json.loads(line[6:])
                    content = chunk["choices"][0].get("delta", {}).get("content", "")
                    if content:
                        yield content
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
    except Exception as e:
        print(f"  [{ts()}] [LLM] Stream error: {e}")
