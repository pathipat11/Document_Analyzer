from __future__ import annotations
from django.conf import settings
from django.db import transaction
from django.utils import timezone

import logging, re

from documents.models import Document
from .text_extractor import extract_text_bytes
from documents.services.analysis.summarizer import summarize_text
from documents.services.analysis.classifier import classify_text
from documents.services.storage.file_organizer import move_document_file_to_type_folder
from documents.models import DocumentChunk
from documents.services.pipeline.chunking import chunk_text
from documents.services.search.search_index import update_document_search_vector

logger = logging.getLogger(__name__)
_NUL_RE = re.compile(r"\x00+")

def sanitize_text(s: str) -> str:
    if not s:
        return ""
    s = _NUL_RE.sub("", s)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    return s


def process_document(doc: Document) -> Document:
    """
    Process a document end to end.

    Slow work (S3 read, text extraction, LLM calls, S3 file move) is kept
    OUTSIDE any database transaction so we never hold a DB connection open
    while waiting on the network. Only the actual writes are wrapped in a
    short atomic block.
    """
    # --- mark as processing (single short write, no transaction needed) ---
    doc.status = "processing"
    doc.error = ""
    doc.save(update_fields=["status", "error"])

    try:
        # --- 1. read file from storage (S3 I/O, no transaction) ---
        with doc.file.open("rb") as f:
            file_bytes = f.read()

        # --- 2. extract + sanitize text (CPU, no transaction) ---
        res = extract_text_bytes(file_bytes, doc.file_ext)
        clean_text = sanitize_text(res.text)

        # --- 3. build chunk contents (CPU, no transaction) ---
        chunk_contents = [
            sanitize_text(c)
            for c in chunk_text(clean_text, chunk_size=900, overlap=150)
            if c
        ]

        # --- 4. LLM summary + classification (network, no transaction) ---
        summary = ""
        document_type = ""
        llm_error = ""
        if getattr(settings, "ENABLE_LLM", True) and clean_text.strip():
            try:
                summary = summarize_text(clean_text, owner=doc.owner) or ""
                document_type = classify_text(clean_text, owner=doc.owner) or ""
            except Exception as e:
                logger.exception("LLM step failed: %s", e)
                llm_error = f"LLM failed: {e}"

        # --- 5. persist text, metadata and chunks atomically (short txn) ---
        doc.extracted_text = clean_text
        doc.word_count = res.word_count
        doc.char_count = res.char_count
        doc.status = "done"
        doc.processed_at = timezone.now()
        doc.error = llm_error

        fields = ["extracted_text", "word_count", "char_count", "status", "processed_at", "error"]
        if summary:
            doc.summary = summary
            fields.append("summary")
        if document_type:
            doc.document_type = document_type
            fields.append("document_type")

        with transaction.atomic():
            doc.save(update_fields=fields)
            DocumentChunk.objects.filter(document=doc).delete()
            DocumentChunk.objects.bulk_create([
                DocumentChunk(document=doc, idx=i + 1, content=c)
                for i, c in enumerate(chunk_contents)
            ])

        # --- 6. update search index (single DB update) ---
        update_document_search_vector(doc.id)

        # --- 7. move file into type-based folder (S3 I/O, no transaction) ---
        move_document_file_to_type_folder(doc)
        return doc

    except Exception as e:
        doc.status = "error"
        doc.error = str(e)
        doc.save(update_fields=["status", "error"])
        raise
