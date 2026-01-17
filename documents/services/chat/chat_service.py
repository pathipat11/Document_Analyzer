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

def _document_context_for_question(doc: Document, question: str) -> str:
    parts = []
    if (doc.summary or "").strip():
        parts.append(f"SUMMARY:\n{doc.summary.strip()}")

    chunks = retrieve_top_chunks(doc.id, question, k=6)
    if chunks:
        lines = []
        for ch in chunks:
            lines.append(f"[C{ch.idx}] {ch.content}")
        parts.append("RELEVANT EXCERPTS:\n" + "\n\n".join(lines))

    return "\n\n".join(parts).strip()

def _looks_general_question(q: str) -> bool:
    ql = (q or "").lower().strip()
    if not ql:
        return True
    # คำถามทั่วไปที่ไม่ควรถูกบังคับให้ตอบจากไฟล์
    general_starts = (
        "สวัสดี", "hello", "hi", "ช่วยคิด", "ไอเดีย", "แนะนำ", "opinion",
        "ทำยังไง", "how to", "what is", "คืออะไร", "แตกต่าง", "ต่างกัน",
    )
    return ql.startswith(general_starts)

def _is_doc_relevant(doc: Document, question: str) -> bool:
    if _looks_general_question(question):
        return False
    chunks = retrieve_top_chunks(doc.id, question, k=3)
    if not chunks:
        return False
    top = chunks[0]
    if top.score < 4:
        return False
    if top.matched_terms < 2:
        return False
    return True



def answer_chat(conv: Conversation, user_question: str) -> str:
    """
    ตอบคำถามจาก conversation นี้ โดยยึด context ของ document/notebook
    """
    q = (user_question or "").strip()
    if not q:
        return ""

    mode = "general"

    if conv.document_id:
        doc = conv.document
        if _is_doc_relevant(doc, q):
            mode = "doc"
            context = _document_context_for_question(doc, q)
        else:
            context = ""  # general mode ไม่ต้องส่ง context
    else:
        # notebook chat ส่วนใหญ่ผู้ใช้คาดหวังอิงไฟล์
        nb = conv.notebook
        mode = "doc"
        context = _notebook_context(nb)


    q_lang = detect_language(q)
    lang = q_lang if q_lang in ("th", "en") else _pick_lang(context, q)

    lang_instruction = "Write in Thai." if lang == "th" else "Write in English."

    # history: เอาเฉพาะท้าย ๆ
    history = _build_history(conv)

    if mode == "doc":
        system = (
            "You are a helpful assistant for a document analyzer app.\n"
            "You must answer primarily using the provided CONTEXT.\n"
            "If you use facts from excerpts, cite them like [C12].\n"
            "Do NOT mention 'based on the file' or 'according to the document' explicitly.\n"
            "Always reply in the same language as the USER QUESTION.\n"
            "If the answer is not in the context, say you don't have enough information "
            "and suggest what to upload or what to ask next.\n"
        )

        user = f"""
    {lang_instruction}

    CONTEXT:
    {_trim(context, max_chars=MAX_CONTEXT_CHARS)}

    USER QUESTION:
    {q}

    Rules:
    - If you use excerpt facts, cite [C#].
    - If missing info in context, say what's missing and suggest next step.
    """
    else:
        system = (
            "You are a helpful assistant.\n"
            "Reply naturally like a normal chat.\n"
            "Do NOT mention documents, context, excerpts, or citations.\n"
            "Always reply in the same language as the USER QUESTION.\n"
        )
        user = f"""
    {lang_instruction}

    USER QUESTION:
    {q}
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

        return (generate_text(system, user, owner=conv.owner, purpose="chat") or "").strip()
    except LLMError as e:
        raise



def answer_chat_stream(conv: Conversation, user_question: str, should_stop=None):
    q = (user_question or "").strip()
    if not q:
        yield ""
        return

    mode = "general"

    if conv.document_id:
        doc = conv.document
        if _is_doc_relevant(doc, q):
            mode = "doc"
            context = _document_context_for_question(doc, q)
        else:
            context = ""  # general mode ไม่ต้องส่ง context
    else:
        # notebook chat ส่วนใหญ่ผู้ใช้คาดหวังอิงไฟล์
        nb = conv.notebook
        mode = "doc"
        context = _notebook_context(nb)


    q_lang = detect_language(q)
    lang = q_lang if q_lang in ("th", "en") else _pick_lang(context, q)
    lang_instruction = "Write in Thai." if lang == "th" else "Write in English."

    history = _build_history(conv)

    if mode == "doc":
        system = (
            "You are a helpful assistant for a document analyzer app.\n"
            "You must answer primarily using the provided CONTEXT.\n"
            "If you use facts from excerpts, cite them like [C12].\n"
            "Do NOT mention 'based on the file' or 'according to the document' explicitly.\n"
            "Always reply in the same language as the USER QUESTION.\n"
            "If the answer is not in the context, say you don't have enough information "
            "and suggest what to upload or what to ask next.\n"
        )

        user = f"""
    {lang_instruction}

    CONTEXT:
    {_trim(context, max_chars=MAX_CONTEXT_CHARS)}

    USER QUESTION:
    {q}

    Rules:
    - If you use excerpt facts, cite [C#].
    - If missing info in context, say what's missing and suggest next step.
    """
    else:
        system = (
            "You are a helpful assistant.\n"
            "Reply naturally like a normal chat.\n"
            "Do NOT mention documents, context, excerpts, or citations.\n"
            "Always reply in the same language as the USER QUESTION.\n"
        )
        user = f"""
    {lang_instruction}

    USER QUESTION:
    {q}
    """

    if history:
        hist_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in history])
        user = f"{user}\n\nCHAT HISTORY (most recent):\n{_trim(hist_text, max_chars=4000)}"
        print("Q:", repr(q))
        print("Q_LANG:", q_lang)
        print("LANG:", lang)
    for t in generate_text_stream(system, user, owner=conv.owner, purpose="chat_stream"):
        if should_stop and should_stop():
            return
        yield t
        
