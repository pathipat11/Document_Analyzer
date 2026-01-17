from __future__ import annotations
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

from .summarizer import summarize_text
from .lang_detect import detect_language
from .title_generator import generate_title
from documents.services.llm.client import generate_text, LLMError
from documents.models import Document

def _pick_language(docs: List[Document]) -> str:
    votes = {"th": 0, "en": 0}
    for d in docs:
        txt = (d.summary or d.extracted_text or "").strip()
        votes[detect_language(txt)] += 1
    return "th" if votes["th"] >= votes["en"] else "en"

def build_combined_summary(docs: List[Document], *, owner=None) -> str:
    """
    Map-Reduce summary:
    - map: ใช้ summary ของแต่ละไฟล์ (ถ้าไม่มี ให้สรุปจาก extracted_text)
    - reduce: รวม map summaries แล้วสรุปภาพรวมอีกครั้ง
    """
    if not docs:
        return ""

    # Map
    per_doc_summaries: List[str] = []
    for d in docs:
        s = (d.summary or "").strip()
        if not s:
            raw = (d.extracted_text or "").strip().replace("\n", " ")
            s = (raw[:400] + "…") if raw else ""

        if s:
            per_doc_summaries.append(f"- {d.file_name}: {s}")

    if not per_doc_summaries:
        return ""

    joined = "\n".join(per_doc_summaries)

    lang = _pick_language(docs)
    lang_instruction = "Write in Thai." if lang == "th" else "Write in English."

    # กันยาวเกิน
    joined = joined[:12000]

    system = "You summarize multiple documents into one consolidated summary."
    user = f"""
Create a consolidated summary from the document summaries below.

Requirements:
- Output MUST be exactly 4-6 bullet points.
- Use "-" at the start of each bullet.
- No intro, no headings, no extra lines.
- Each bullet captures a key theme across documents.
- {lang_instruction}

DOCUMENT SUMMARIES:
{joined}
"""
    try:
        return (generate_text(system, user, owner=owner, purpose="combined") or "").strip()
    except LLMError as e:
        logger.warning("combined_summary failed: %s", e)
        return "(combined summary not available: quota reached)"

def build_combined_title_and_summary(docs: List[Document], *, owner=None) -> Tuple[str, str]:
    if not docs:
        return ("Combined Summary", "")

    # map: ใช้ summary ของแต่ละไฟล์ (ถ้าไม่มีให้สรุป)
    per_doc = []
    for d in docs:
        s = (d.summary or "").strip()
        if not s:
            raw = (d.extracted_text or "").strip().replace("\n", " ")
            s = (raw[:400] + "…") if raw else ""

        if s:
            per_doc.append(f"- {d.file_name}: {s}")

    joined = "\n".join(per_doc).strip()
    if not joined:
        return ("Combined Summary", "")

    title = generate_title(joined, owner=owner)

    # reduce summary จาก joined
    lang = "th" if detect_language(joined) == "th" else "en"
    lang_instruction = "Write in Thai." if lang == "th" else "Write in English."

    joined = joined[:12000]

    system = "You summarize multiple documents into one consolidated summary."
    user = f"""
Create a consolidated summary from the document summaries below.

Requirements:
- Exactly 4-6 bullet points.
- No intro, no disclaimers.
- {lang_instruction}

DOCUMENT SUMMARIES:
{joined}
"""
    try:
        combined = (generate_text(system, user, owner=owner, purpose="combined") or "").strip()
    except LLMError as e:
        logger.warning("combined_summary failed: %s", e)
        return (title or "Combined Summary", "(combined summary not available: quota reached)")
    return (title, combined)