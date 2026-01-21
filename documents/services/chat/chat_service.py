from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from documents.services.llm.client import generate_text, LLMError, generate_text_stream
from documents.services.analysis.lang_detect import detect_language
from documents.services.pipeline.retrieval import retrieve_top_chunks
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

def _looks_general_question(q: str) -> bool:
    ql = (q or "").strip().lower()
    if not ql:
        return True

    greetings = ("สวัสดี", "hello", "hi", "hey")
    if ql.startswith(greetings) and len(ql) <= 12:
        return True

    if len(ql) <= 10:
        return True

    return False

def _build_context(conv: Conversation, question: str) -> str:
    q = (question or "").strip()
    if not q:
        return ""

    if conv.document_id:
        doc = conv.document
        parts = []

        if (doc.summary or "").strip():
            parts.append(f"SUMMARY:\n{doc.summary.strip()}")

        chunks = retrieve_top_chunks(doc.id, q, k=6)
        if chunks:
            lines = [f"[D{doc.id}-C{ch.idx}] {ch.content}" for ch in chunks]
            parts.append("RELEVANT EXCERPTS:\n" + "\n\n".join(lines))

        return "\n\n".join(parts).strip()

    if conv.notebook_id:
        nb = conv.notebook
        parts = [_notebook_context(nb)]

        scored_all = []
        for d in nb.documents.all():
            for ch in retrieve_top_chunks(d.id, q, k=3):
                scored_all.append((ch.score, d.id, d.file_name, ch.idx, ch.content))

        scored_all.sort(key=lambda x: x[0], reverse=True)
        top = scored_all[:6]
        if top:
            lines = []
            for _, doc_id, fname, idx, content in top:
                lines.append(f"[D{doc_id}-C{idx}] ({fname}) {content}")
            parts.append("RELEVANT EXCERPTS:\n" + "\n\n".join(lines))

        return "\n\n".join([p for p in parts if p]).strip()

    return ""

def _system(has_source: bool) -> str:
    if has_source:
        return (
            "You are a helpful assistant.\n"
            "You may receive optional CONTEXT extracted from the user's document/notebook.\n"
            "Use CONTEXT as the primary source of truth.\n"
            "If you use any factual details from RELEVANT EXCERPTS, cite them like [D12-C3].\n"
            "If the answer is not supported by the CONTEXT, say you don't have enough information.\n"
            "Do NOT mention documents, files, context, or excerpts explicitly.\n"
            "Always reply in the same language as the USER QUESTION.\n"
        )
    return (
        "You are a helpful assistant.\n"
        "Answer naturally.\n"
        "Always reply in the same language as the USER QUESTION.\n"
    )



def answer_chat(conv: Conversation, user_question: str) -> str:
    q = (user_question or "").strip()
    if not q:
        return ""

    q_lang = detect_language(q)
    lang = q_lang if q_lang in ("th", "en") else "th"

    lang_instruction = "Write in Thai." if lang == "th" else "Write in English."

    history = _build_history(conv)
    context = _build_context(conv, q)

    has_source = bool(conv.document_id or conv.notebook_id)
    system = _system(has_source)
    
    if has_source and not context:
        system += "If there is no CONTEXT, reply that you don't have enough information.\n"

    user = f"""
user = f"{lang_instruction}\n\nUSER QUESTION:\n{q}".strip()
if context:
    user = f"{lang_instruction}\n\nCONTEXT:\n{_trim(context, max_chars=MAX_CONTEXT_CHARS)}\n\nUSER QUESTION:\n{q}".strip()

CONTEXT (optional):
{_trim(context, max_chars=MAX_CONTEXT_CHARS) if context else "(none)"}

USER QUESTION:
{q}
""".strip()

    if history:
        hist_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in history])
        user += f"\n\nCHAT HISTORY (most recent):\n{_trim(hist_text, max_chars=4000)}"

    return (generate_text(system, user, owner=conv.owner, purpose="chat") or "").strip()

def answer_chat_stream(conv: Conversation, user_question: str, should_stop=None):
    q = (user_question or "").strip()
    if not q:
        return

    q_lang = detect_language(q)
    lang = q_lang if q_lang in ("th", "en") else "th"
    lang_instruction = "Write in Thai." if lang == "th" else "Write in English."

    history = _build_history(conv)
    context = _build_context(conv, q)

    has_source = bool(conv.document_id or conv.notebook_id)
    system = _system(has_source)

    user = f"""
{lang_instruction}

CONTEXT (optional):
{_trim(context, max_chars=MAX_CONTEXT_CHARS) if context else "(none)"}

USER QUESTION:
{q}
""".strip()
    if history:
        hist_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in history])
        user += f"\n\nCHAT HISTORY (most recent):\n{_trim(hist_text, max_chars=4000)}"

    for t in generate_text_stream(system, user, owner=conv.owner, purpose="chat_stream"):
        if should_stop and should_stop():
            return
        yield t