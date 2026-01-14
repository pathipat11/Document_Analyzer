import logging
from documents.services.llm.client import generate_text, LLMError
from .lang_detect import detect_language

logger = logging.getLogger(__name__)

def summarize_text(text: str, *, owner=None) -> str:
    clean = (text or "").strip()
    if not clean:
        return ""

    clean = _trim_for_summary(clean, max_chars=12000)
    lang = detect_language(clean)
    lang_instruction = "Write in Thai." if lang == "th" else "Write in English."

    system = "You summarize documents for a web app."
    user = f"""
Write a clean summary in exactly 2-3 sentences. {lang_instruction}

Constraints:
- No intro like "Here is a summary".
- No disclaimers.
- Output ONLY the summary text.

DOCUMENT:
{clean}
"""
    try:
        return (generate_text(system, user, owner=owner, purpose="summarize") or "").strip()
    except LLMError as e:
        logger.exception("LLM summarize failed: %s", e)
        raise


def _trim_for_summary(text: str, max_chars: int = 12000) -> str:
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    head = text[:half]
    tail = text[-half:]
    return head + "\n\n...[TRUNCATED]...\n\n" + tail
