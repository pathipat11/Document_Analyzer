from __future__ import annotations
from typing import List, Tuple

from .summarizer import summarize_text
from .lang_detect import detect_language
from .title_generator import generate_title
from .llm_client import generate_text, LLMError
from documents.models import Document


def _pick_language(docs: List[Document]) -> str:
    # ถ้าเอกสารส่วนใหญ่เป็นไทย -> th ไม่งั้น en
    votes = {"th": 0, "en": 0}
    for d in docs:
        votes[detect_language(d.extracted_text or "")] += 1
    return "th" if votes["th"] >= votes["en"] else "en"


def build_combined_summary(docs: List[Document]) -> str:
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
        if not s and (d.extracted_text or "").strip():
            s = summarize_text(d.extracted_text)
        if s:
            per_doc_summaries.append(f"- {d.file_name}: {s}")

    if not per_doc_summaries:
        return ""

    joined = "\n".join(per_doc_summaries)

    # Reduce: สรุปรวมจาก summary แต่ละไฟล์ (สั้นลง)
    lang = _pick_language(docs)
    lang_instruction = "Write in Thai." if lang == "th" else "Write in English."

    # กันยาวเกิน
    joined = joined[:12000]

    system = "You summarize multiple documents into one consolidated summary."
    user = f"""
Create a consolidated summary from the document summaries below.

Requirements:
- Exactly 4-6 bullet points.
- Each bullet captures a key theme across documents.
- No intro, no disclaimers.
- {lang_instruction}

DOCUMENT SUMMARIES:
{joined}
"""
    try:
        return (generate_text(system, user) or "").strip()
    except LLMError:
        return ""

def build_combined_title_and_summary(docs: List[Document]) -> Tuple[str, str]:
    if not docs:
        return ("Combined Summary", "")

    # map: ใช้ summary ของแต่ละไฟล์ (ถ้าไม่มีให้สรุป)
    per_doc = []
    for d in docs:
        s = (d.summary or "").strip()
        if not s and (d.extracted_text or "").strip():
            s = summarize_text(d.extracted_text)
        if s:
            per_doc.append(f"- {d.file_name}: {s}")

    joined = "\n".join(per_doc).strip()
    if not joined:
        return ("Combined Summary", "")

    # generate title จาก joined (สั้นๆ)
    title = generate_title(joined)

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
        combined = (generate_text(system, user) or "").strip()
    except LLMError:
        combined = ""

    return (title, combined)