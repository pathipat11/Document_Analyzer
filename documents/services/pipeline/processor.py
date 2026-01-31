from __future__ import annotations
from django.conf import settings
from django.db import transaction
from django.utils import timezone

import logging, re

from documents.models import Document
from .text_extractor import extract_text, extract_text_bytes
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

@transaction.atomic
def process_document(doc: Document) -> Document:
    doc.status = "processing"
    doc.error = ""
    doc.save(update_fields=["status", "error"])

    try:
        with doc.file.open("rb") as f:
            file_bytes = f.read()

        res = extract_text_bytes(file_bytes, doc.file_ext)

        clean_text = sanitize_text(res.text)
        
        doc.extracted_text = clean_text
        doc.word_count = res.word_count
        doc.char_count = res.char_count

        # build chunks
        DocumentChunk.objects.filter(document=doc).delete()
        chunks = chunk_text(clean_text, chunk_size=900, overlap=150)
        chunks = [sanitize_text(c) for c in chunks if c] 
        DocumentChunk.objects.bulk_create([
            DocumentChunk(document=doc, idx=i+1, content=c)
            for i, c in enumerate(chunks)
        ])

        if getattr(settings, "ENABLE_LLM", True) and clean_text.strip():
            try:
                s = summarize_text(clean_text, owner=doc.owner)
                if s:  # ได้ summary จริงค่อยทับ
                    doc.summary = s

                t = classify_text(clean_text, owner=doc.owner)
                if t:
                    doc.document_type = t

            except Exception as e:
                logger.exception("LLM step failed: %s", e)
                doc.error = f"LLM failed: {e}"


        doc.status = "done"
        doc.processed_at = timezone.now()

        fields = ["extracted_text","word_count","char_count","status","processed_at","error"]

        if doc.summary:
            fields.append("summary")
        if doc.document_type:
            fields.append("document_type")

        doc.save(update_fields=fields)

        update_document_search_vector(doc.id)
        move_document_file_to_type_folder(doc)
        return doc

    except Exception as e:
        doc.status = "error"
        doc.error = str(e)
        doc.save(update_fields=["status", "error"])
        raise