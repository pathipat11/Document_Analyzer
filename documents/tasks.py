from __future__ import annotations

import logging

from celery import shared_task

from documents.models import Document
from documents.services.pipeline.processor import process_document

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=10,
    acks_late=True,
)
def process_document_task(self, doc_id: int):
    """
    Background entry point for the document pipeline.

    Loads the document fresh inside the worker and runs the same
    process_document() used in synchronous mode. On unexpected errors the
    document status is already set to "error" by process_document(); we retry
    a couple of times for transient failures (e.g. network blips).
    """
    try:
        doc = Document.objects.get(pk=doc_id)
    except Document.DoesNotExist:
        logger.warning("process_document_task: document %s no longer exists", doc_id)
        return None

    try:
        process_document(doc)
    except Exception as exc:  # noqa: BLE001 - we want to retry on any failure
        logger.exception("process_document_task failed for doc %s", doc_id)
        raise self.retry(exc=exc)

    return doc_id


@shared_task
def build_combined_summary_task(processed_doc_ids, owner_id, title=""):
    """
    Build a CombinedSummary after a group of documents finished processing.

    Used as the callback of a Celery chord, so ``processed_doc_ids`` is the
    list of return values from the document-processing tasks (doc ids, with
    ``None`` for any that disappeared).
    """
    from django.contrib.auth import get_user_model
    from documents.models import CombinedSummary
    from documents.services.analysis.combined_summarizer import (
        build_combined_title_and_summary,
    )

    doc_ids = [d for d in (processed_doc_ids or []) if d]
    if len(doc_ids) < 2:
        logger.info("build_combined_summary_task: not enough docs to combine")
        return None

    User = get_user_model()
    try:
        owner = User.objects.get(pk=owner_id)
    except User.DoesNotExist:
        logger.warning("build_combined_summary_task: owner %s missing", owner_id)
        return None

    docs = list(
        Document.objects.filter(owner=owner, id__in=doc_ids).order_by("-uploaded_at")
    )
    if len(docs) < 2:
        return None

    ai_title, combined_text = build_combined_title_and_summary(docs, owner=owner)
    cs = CombinedSummary.objects.create(
        owner=owner,
        title=(title or "").strip() or ai_title,
        combined_summary=combined_text,
        doc_count=len(docs),
        total_words=sum(d.word_count for d in docs),
    )
    cs.documents.set(docs)
    return cs.id
