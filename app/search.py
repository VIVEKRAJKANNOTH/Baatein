"""
search.py — DuckDuckGo web search and transcript cleanup.
"""

from duckduckgo_search import DDGS

# ─── Filler words to strip from transcripts before searching ───
FILLER_WORDS = {
    'hmm', 'hm', 'um', 'uh', 'ah', 'okay', 'ok', 'like', 'yeah', 'yes', 'no',
    'right', 'so', 'well', 'actually', 'basically', 'you know', 'i mean',
    'let me think', 'wait', 'hold on', 'alla', 'adu', 'ennu', 'aanu',
    'hmm.', 'okay.', 'yeah.', 'yes.', 'no.', 'super', 'super.',
}


def web_search(query: str, max_results: int = 3) -> str:
    """Search DuckDuckGo and return formatted results."""
    try:
        results = DDGS().text(query, max_results=max_results)
        if not results:
            return "No results found."
        formatted = []
        for r in results:
            formatted.append(f"- {r['title']}: {r['body']}")
        return "\n".join(formatted)
    except Exception as e:
        return f"Search error: {e}"


def clean_for_search(transcript: str) -> str:
    """Clean transcript for use as a search query.
    Strips fillers, keeps the meaningful question/content."""
    words = transcript.split()
    cleaned = []
    for w in words:
        if w.lower().strip('.,!?') in FILLER_WORDS:
            continue
        cleaned.append(w)
    result = ' '.join(cleaned).strip()
    # If we stripped too much, fall back to original
    if len(result) < 5:
        return transcript.strip()
    return result


def query_similarity(q1: str, q2: str) -> float:
    """Simple word overlap ratio between two queries."""
    w1 = set(q1.lower().split())
    w2 = set(q2.lower().split())
    if not w1 or not w2:
        return 0.0
    return len(w1 & w2) / max(len(w1), len(w2))
