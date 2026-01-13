from __future__ import annotations
from django.conf import settings
from django.db import transaction
from django.utils import timezone

import logging

from documents.models import Document
from .text_extractor import extract_text
from documents.services.analysis.summarizer import summarize_text
from documents.services.analysis.classifier import classify_text
from documents.services.storage.file_organizer import move_document_file_to_type_folder
from documents.models import DocumentChunk
from documents.services.pipeline.chunking import chunk_text

logger = logging.getLogger(__name__)

@transaction.atomic
def process_document(doc: Document) -> Document:
    doc.status = "processing"
    doc.error = ""
    doc.save(update_fields=["status", "error"])

    try:
        res = extract_text(doc.file.path, doc.file_ext)
        doc.extracted_text = res.text
        doc.word_count = res.word_count
        doc.char_count = res.char_count

        # build chunks
        DocumentChunk.objects.filter(document=doc).delete()
        chunks = chunk_text(res.text, chunk_size=900, overlap=150)
        DocumentChunk.objects.bulk_create([
            DocumentChunk(document=doc, idx=i+1, content=c)
            for i, c in enumerate(chunks)
        ])

        if getattr(settings, "ENABLE_LLM", True) and res.text.strip():
            doc.summary = summarize_text(res.text, owner=doc.owner)
            doc.document_type = classify_text(res.text, owner=doc.owner)

        doc.status = "done"
        doc.processed_at = timezone.now()
        doc.save(update_fields=[
            "extracted_text","word_count","char_count",
            "summary","document_type","status","processed_at"
        ])

        move_document_file_to_type_folder(doc)
        return doc

    except Exception as e:
        doc.status = "error"
        doc.error = str(e)
        doc.save(update_fields=["status", "error"])
        raise