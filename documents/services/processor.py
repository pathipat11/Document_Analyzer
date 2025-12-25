from __future__ import annotations
from django.conf import settings
from django.db import transaction

import logging

from documents.models import Document
from .text_extractor import extract_text
from .summarizer import summarize_text
from .classifier import classify_text

logger = logging.getLogger(__name__)

@transaction.atomic
def process_document(doc: Document) -> Document:
    res = extract_text(doc.file.path, doc.file_ext)

    doc.extracted_text = res.text
    doc.word_count = res.word_count
    doc.char_count = res.char_count

    if getattr(settings, "ENABLE_LLM", True) and res.text.strip():
        logger.info("LLM: generating summary/type for doc_id=%s model=%s",
                    doc.id, getattr(settings, "OLLAMA_MODEL", ""))
        doc.summary = summarize_text(res.text)
        doc.document_type = classify_text(res.text)
        logger.info("LLM: done doc_id=%s summary_len=%s type=%s",
                    doc.id, len(doc.summary or ""), doc.document_type)

    doc.save(update_fields=[
        "extracted_text",
        "word_count",
        "char_count",
        "summary",
        "document_type",
    ])
    return doc
