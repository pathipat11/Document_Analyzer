from __future__ import annotations
from documents.services.llm.client import generate_text, LLMError
from .lang_detect import detect_language


def generate_title(context_text: str, *, owner=None) -> str:
    clean = (context_text or "").strip()
    if not clean:
        return "Notebook Summary"

    lang = detect_language(clean)
    lang_instruction = "Write in Thai." if lang == "th" else "Write in English."

    # กันยาวเกิน
    clean = clean[:8000]

    system = "You generate short, clear titles for a collection of documents."
    user = f"""
Generate a concise notebook title (max 8 words).
Rules:
- Output only the title text
- No quotes
- No emojis
- No trailing punctuation
- {lang_instruction}

TEXT:
{clean}
"""
    try:
        t = (generate_text(system, user, owner=owner, purpose="title") or "").strip()
        # กันโมเดลตอบหลายบรรทัด
        t = t.splitlines()[0].strip()
        # กัน punctuation ปลาย
        t = t.rstrip(" .,:;\"'`")
        return (t[:120] or "Notebook Summary")
    except LLMError:
        return "Notebook Summary"
