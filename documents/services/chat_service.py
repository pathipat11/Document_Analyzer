from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .llm_client import generate_text, LLMError, generate_text_stream
from .lang_detect import detect_language
from documents.models import Conversation, Message, Document, CombinedSummary


# กัน prompt ยาวเกิน (Ollama บางรุ่นหลุดง่ายถ้ายาวมาก)
MAX_CONTEXT_CHARS = 12000
MAX_HISTORY_TURNS = 8  # เอาเฉพาะท้าย ๆ (user+assistant) เพื่อคุมความยาว


def _trim(text: str, max_chars: int = MAX_CONTEXT_CHARS) -> str:
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t
    half = max_chars // 2
    return t[:half] + "\n\n...[TRUNCATED]...\n\n" + t[-half:]


def _pick_lang(*texts: str) -> str:
    # ถ้ามีข้อความไทยเยอะ -> th
    blob = "\n".join([(t or "") for t in texts]).strip()
    if not blob:
        return "en"
    return "th" if detect_language(blob) == "th" else "en"


def _build_history(conv: Conversation) -> List[dict]:
    """
    เอา history ล่าสุดเป็น messages สำหรับ LLM
    - เอาเฉพาะ user/assistant
    - จำกัดจำนวน turn
    """
    qs = conv.messages.filter(role__in=["user", "assistant"]).order_by("-created_at")
    items = list(qs[: MAX_HISTORY_TURNS * 2])  # เผื่อ role สลับ
    items.reverse()

    out = []
    for m in items:
        out.append({"role": m.role, "content": (m.content or "").strip()})
    return out


def _document_context(doc: Document) -> str:
    """
    Context สำหรับ document เดี่ยว:
    - summary (ถ้ามี)
    - extracted_text (ตัดให้สั้น)
    """
    parts = []
    if (doc.summary or "").strip():
        parts.append(f"SUMMARY:\n{doc.summary.strip()}")
    if (doc.extracted_text or "").strip():
        parts.append(f"DOCUMENT TEXT:\n{_trim(doc.extracted_text)}")
    return "\n\n".join(parts).strip()


def _notebook_context(nb: CombinedSummary) -> str:
    """
    Context สำหรับ notebook (combined):
    - title
    - combined_summary (bullet)
    - per-doc summary (ชื่อไฟล์ + summary) เพื่อให้ตอบละเอียดขึ้น
    """
    parts = [f"NOTEBOOK TITLE:\n{nb.title}"]

    if (nb.combined_summary or "").strip():
        parts.append(f"COMBINED SUMMARY:\n{nb.combined_summary.strip()}")

    # เพิ่ม per-doc summaries เพื่อให้ถามเจาะไฟล์ได้บ้าง
    per_doc_lines = []
    for d in nb.documents.all().order_by("-uploaded_at"):
        s = (d.summary or "").strip()
        if s:
            per_doc_lines.append(f"- {d.file_name}: {s}")
    if per_doc_lines:
        joined = "\n".join(per_doc_lines)
        parts.append(f"PER-DOCUMENT SUMMARIES:\n{_trim(joined, max_chars=8000)}")

    return "\n\n".join(parts).strip()


def answer_chat(conv: Conversation, user_question: str) -> str:
    """
    ตอบคำถามจาก conversation นี้ โดยยึด context ของ document/notebook
    """
    q = (user_question or "").strip()
    if not q:
        return ""

    # context ตาม target
    if conv.document_id:
        doc = conv.document
        context = _document_context(doc)
    else:
        nb = conv.notebook
        context = _notebook_context(nb)

    q_lang = detect_language(q)
    lang = q_lang if q_lang in ("th", "en") else _pick_lang(context, q)

    lang_instruction = "Write in Thai." if lang == "th" else "Write in English."

    # history: เอาเฉพาะท้าย ๆ
    history = _build_history(conv)

    system = (
        "You are a helpful assistant for a local document analyzer app.\n"
        "You must answer using ONLY the provided CONTEXT.\n"
        "Always reply in the same language as the USER QUESTION.\n"
        "If the answer is not in the context, say you don't have enough information "
        "and suggest what to upload or what to ask next.\n"
        "Be concise, but clear.\n"
    )

    # เราจะส่ง history + question เป็น messages ต่อท้าย
    # โดย pack context เข้าไปใน system/user เพื่อคุมทิศ
    user = f"""
{lang_instruction}

CONTEXT (authoritative):
{_trim(context, max_chars=MAX_CONTEXT_CHARS)}

USER QUESTION:
{q}

Rules:
- Use ONLY the context above.
- No disclaimers.
- If missing info, say what is missing and suggest next step.
"""

    try:
        # ถ้าอยาก include history แบบ messages หลายอัน:
        # เราจะรวม history เป็นข้อความเดียวเพื่อใช้ generate_text ที่รับ system+user
        # (โครง llm_client ของคุณรองรับ system+user เท่านั้น)
        if history:
            hist_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in history])
            user = f"{user}\n\nCHAT HISTORY (most recent):\n{_trim(hist_text, max_chars=4000)}"
        print("Q:", repr(q))
        print("Q_LANG:", q_lang)
        print("LANG:", lang)

        return (generate_text(system, user) or "").strip()
    except LLMError:
        return ""

def answer_chat_stream(conv: Conversation, user_question: str, should_stop=None):
    q = (user_question or "").strip()
    if not q:
        yield ""
        return

    if conv.document_id:
        doc = conv.document
        context = _document_context(doc)
    else:
        nb = conv.notebook
        context = _notebook_context(nb)

    q_lang = detect_language(q)
    lang = q_lang if q_lang in ("th", "en") else _pick_lang(context, q)
    lang_instruction = "Write in Thai." if lang == "th" else "Write in English."

    history = _build_history(conv)

    system = (
        "You are a helpful assistant for a local document analyzer app.\n"
        "You must answer using ONLY the provided CONTEXT.\n"
        "Always reply in the same language as the USER QUESTION.\n"
        "If the answer is not in the context, say you don't have enough information "
        "and suggest what to upload or what to ask next.\n"
        "Be concise, but clear.\n"
    )

    user = f"""
{lang_instruction}

CONTEXT (authoritative):
{_trim(context, max_chars=MAX_CONTEXT_CHARS)}

USER QUESTION:
{q}

Rules:
- Use ONLY the context above.
- No disclaimers.
- If missing info, say what is missing and suggest next step.
"""

    if history:
        hist_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in history])
        user = f"{user}\n\nCHAT HISTORY (most recent):\n{_trim(hist_text, max_chars=4000)}"

    for t in generate_text_stream(system, user):
        if should_stop and should_stop():
            return
        yield t