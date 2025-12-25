from __future__ import annotations
from .llm_client import generate_text, LLMError


def summarize_text(text: str) -> str:
    clean = (text or "").strip()
    if not clean:
        return ""

    clean = _trim_for_summary(clean, max_chars=12000)

    system = "You summarize documents for a web app."
    user = f"""
    Write a clean summary in exactly 2-3 sentences.

    Constraints:
    - Do NOT add any intro like "Here is a summary".
    - Do NOT add disclaimers like "Please note".
    - Do NOT mention YOLO unless it appears in the text.
    - Output ONLY the summary text (no bullet points, no quotes).

    DOCUMENT:
    {clean}
    """

    try:
        out = generate_text(system, user)
        # กันโมเดลพูดเยิ่นเย้อ: ตัดบรรทัดว่างท้ายๆ
        return (out or "").strip()
    except LLMError:
        return ""


def _trim_for_summary(text: str, max_chars: int = 12000) -> str:
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    head = text[:half]
    tail = text[-half:]
    return head + "\n\n...[TRUNCATED]...\n\n" + tail
