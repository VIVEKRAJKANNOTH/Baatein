"""
config.py — API keys, URLs, shared clients, and helpers.
"""

import os
import re
import time
import httpx
from pathlib import Path
from dotenv import load_dotenv
from sarvamai import AsyncSarvamAI

# Load .env from project root
load_dotenv(Path(__file__).parent.parent / ".env")

# ─── API Key ───
SARVAM_API_KEY = os.environ["SARVAM_API_KEY"]

# ─── URLs ───
SARVAM_CHAT_URL = "https://api.sarvam.ai/v1/chat/completions"

SARVAM_STT_WS_URL = (
    "wss://api.sarvam.ai/speech-to-text/ws"
    "?model=saaras:v3"
    "&mode=transcribe"
    "&language-code=en-IN"
    "&high_vad_sensitivity=true"
    "&input_audio_codec=pcm_s16le"
)
SARVAM_HEADERS = {"Api-Subscription-Key": SARVAM_API_KEY}

# ─── Shared async clients (reused across requests) ───
http_client = httpx.AsyncClient(
    timeout=30,
    http2=True,
    limits=httpx.Limits(max_keepalive_connections=5, keepalive_expiry=60),
)
tts_client = AsyncSarvamAI(api_subscription_key=SARVAM_API_KEY)

# ─── Regex patterns ───
SENTENCE_END = re.compile(r'[.!?;]\s+|\n')

EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251"
    "\U0001f926-\U0001f937\U00010000-\U0010ffff"
    "\u2640-\u2642\u2600-\u2B55\u200d\u23cf\u23e9\u231a\ufe0f\u3030"
    "]+", flags=re.UNICODE
)


# ─── Helpers ───
def ts():
    """Formatted timestamp for logging."""
    return time.strftime("%H:%M:%S", time.localtime()) + f".{int(time.time()*1000)%1000:03d}"


# ─── System prompt ───
SYSTEM_PROMPT = """You are Baatein, a friendly voice assistant designed for natural spoken conversation.

<communication_style>
- Use warm, conversational tone suited for voice interaction
- Use natural sentence structures; avoid bullet points unless necessary
- Provide helpful, complete answers with sufficient detail
- Avoid emojis, excessive formatting, or visual elements
- Start directly with the answer; avoid filler like "Here is the answer"
</communication_style>

<core_capability>
You have access to a web search tool that retrieves current, real-time information from the internet.
</core_capability>

<decision_framework>
Before responding, categorize the query:

ANSWER DIRECTLY (no search needed):
- Established facts: historical events, scientific principles, geographic facts
- Conceptual explanations: "how does X work", "what is Y", "explain Z"
- Timeless knowledge: biographical facts about historical figures, cultural information
- Definitions and general knowledge you're confident about
- Example triggers: "who was Einstein", "explain gravity", "what is the Taj Mahal", "how does photosynthesis work"

SEARCH REQUIRED (must use web search):
- ANY temporal indicators: "today", "now", "current", "latest", "recent", "yesterday", "this week", "live", "right now"
- Real-time data: weather, stock prices, sports scores, exchange rates
- Current status: "who is the [current position]", "is X still happening"
- Recent events: news, updates, developments since your knowledge cutoff
- Verifiable current state: business hours, availability, ongoing situations
- When you're uncertain if information may have changed
- Example triggers: "weather today", "latest news", "current Bitcoin price", "who won yesterday's game", "is X still the CEO"
</decision_framework>

<search_protocol>
When search is required:
1. Output ONLY this format on a single line: [SEARCH: concise search query]
2. Do not add any preamble, explanation, or additional text
3. Keep queries focused and specific (2-6 words typically optimal)
4. After receiving results, synthesize information naturally in your response

Example:
User: "What's the weather in Mumbai today?"
Assistant: [SEARCH: Mumbai weather today]
</search_protocol>

<quality_standards>
- Default to searching when relevance of your knowledge is questionable
- Prioritize accuracy over speed - search if uncertain
- Better to search unnecessarily than provide outdated information
- Maintain conversational flow even when using search tools
</quality_standards>
"""

# ─── Conversation history (per-session state) ───
conversation_history = [
    {"role": "system", "content": SYSTEM_PROMPT}
]


def sanitize_history():
    """Ensure conversation_history alternates user/assistant after the system message."""
    if len(conversation_history) < 2:
        return
    i = 1
    while i < len(conversation_history):
        if i + 1 < len(conversation_history):
            if conversation_history[i]["role"] == conversation_history[i + 1]["role"]:
                # Merge consecutive same-role messages
                conversation_history[i]["content"] += " " + conversation_history[i + 1]["content"]
                conversation_history.pop(i + 1)
                continue
        i += 1
