from __future__ import annotations
from .llm_client import generate_text, LLMError

DOC_TYPES = {"invoice", "announcement", "policy", "other"}

def classify_text(text: str) -> str:
    clean = (text or "").strip()
    if not clean:
        return "other"

    clean = clean[:8000]

    system = "You are a strict document classifier."
    user = f"""
Classify this document into one of these labels:
invoice, announcement, policy, other

Rules:
- Reply with ONE WORD ONLY (exactly one of the labels).
- No extra text.

DOCUMENT:
{clean}
"""

    try:
        out = generate_text(system, user).lower().strip()
        # บางทีโมเดลอาจตอบ "invoice." → ตัด punctuation ง่ายๆ
        out = out.strip().strip(" .,:;\"'")
        return out if out in DOC_TYPES else "other"
    except LLMError:
        return "other"
