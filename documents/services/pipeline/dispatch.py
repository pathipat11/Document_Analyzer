from __future__ import annotations

from django.conf import settings

from documents.models import Document
from documents.services.pipeline.processor import process_document


def enqueue_processing(doc: Document) -> bool:
    """
    Process a document, choosing sync or async based on configuration.

    Returns True if the work was handed off to a background worker, or
    False if it was processed synchronously (and is already finished).

    When PROCESS_DOCUMENTS_ASYNC is enabled the document is marked "queued"
    and a Celery task is dispatched. Otherwise it is processed inline, which
    preserves the original behaviour for setups without a broker.
    """
    if getattr(settings, "PROCESS_DOCUMENTS_ASYNC", False):
        # Import here so environments without Celery installed can still run
        # synchronously without importing the broker stack at module load.
        from documents.tasks import process_document_task

        if doc.status != "queued":
            doc.status = "queued"
            doc.save(update_fields=["status"])

        process_document_task.delay(doc.id)
        return True

    process_document(doc)
    return False
