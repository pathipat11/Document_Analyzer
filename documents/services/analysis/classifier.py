from __future__ import annotations
from documents.services.llm.client import generate_text, LLMError

LABELS = ["invoice","announcement","policy","proposal","report","research","resume","other"]
DOC_TYPES = set(LABELS)

def classify_text(text: str, *, owner=None) -> str:
    clean = (text or "").strip()
    if not clean:
        return "other"

    clean = clean[:8000]

    system = "You are a strict document classifier."
    user = f"""
Classify this document into one of these labels:
{", ".join(LABELS)}

Rules:
- Reply with ONE WORD ONLY (exactly one of the labels).
- No extra text.

DOCUMENT:
{clean}
"""

    try:
        out = (generate_text(system, user, owner=owner, purpose="classify") or "").lower().strip()
        out = out.strip().strip(" .,:;\"'")
        return out if out in DOC_TYPES else "other"
    except LLMError:
        return "other"