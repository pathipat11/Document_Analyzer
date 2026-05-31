from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from documents.models import CombinedSummary, Document
from documents.services.pipeline.dispatch import enqueue_processing

User = get_user_model()

INMEMORY_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(
    STORAGES=INMEMORY_STORAGES,
    ENABLE_LLM=False,
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class DispatchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="async", password="pw")

    def _make_doc(self, content="async content here", name="a.txt") -> Document:
        doc = Document.objects.create(
            owner=self.user, file_name=name, file_ext="txt"
        )
        doc.file.save(name, ContentFile(content.encode("utf-8")), save=True)
        return doc

    @override_settings(PROCESS_DOCUMENTS_ASYNC=False)
    def test_sync_mode_processes_inline(self):
        doc = self._make_doc()
        is_async = enqueue_processing(doc)
        self.assertFalse(is_async)
        doc.refresh_from_db()
        self.assertEqual(doc.status, "done")

    @override_settings(PROCESS_DOCUMENTS_ASYNC=True)
    def test_async_mode_runs_task_eagerly(self):
        doc = self._make_doc()
        is_async = enqueue_processing(doc)
        self.assertTrue(is_async)
        # In eager mode the task runs synchronously, so it should be done.
        doc.refresh_from_db()
        self.assertEqual(doc.status, "done")

    def test_task_handles_missing_document(self):
        from documents.tasks import process_document_task

        # Should not raise for a non-existent id.
        result = process_document_task.run(999999)
        self.assertIsNone(result)


@override_settings(
    STORAGES=INMEMORY_STORAGES,
    ENABLE_LLM=False,
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class CombinedSummaryTaskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="combine", password="pw")

    def _make_doc(self, name) -> Document:
        doc = Document.objects.create(
            owner=self.user, file_name=name, file_ext="txt"
        )
        doc.file.save(name, ContentFile(b"some content for combining"), save=True)
        return doc

    def test_build_combined_summary_task_creates_notebook(self):
        from documents.tasks import process_document_task, build_combined_summary_task

        d1 = self._make_doc("one.txt")
        d2 = self._make_doc("two.txt")
        process_document_task.run(d1.id)
        process_document_task.run(d2.id)

        # Mock the LLM-backed builder so the test stays hermetic (no network).
        with mock.patch(
            "documents.services.analysis.combined_summarizer.build_combined_title_and_summary",
            return_value=("AI Title", "- point one\n- point two"),
        ):
            cs_id = build_combined_summary_task.run(
                [d1.id, d2.id], self.user.id, "My Notebook"
            )

        self.assertIsNotNone(cs_id)
        cs = CombinedSummary.objects.get(pk=cs_id)
        self.assertEqual(cs.title, "My Notebook")
        self.assertEqual(cs.doc_count, 2)
        self.assertEqual(cs.documents.count(), 2)

    def test_build_combined_summary_task_uses_ai_title_when_blank(self):
        from documents.tasks import process_document_task, build_combined_summary_task

        d1 = self._make_doc("a.txt")
        d2 = self._make_doc("b.txt")
        process_document_task.run(d1.id)
        process_document_task.run(d2.id)

        with mock.patch(
            "documents.services.analysis.combined_summarizer.build_combined_title_and_summary",
            return_value=("AI Generated Title", "- summary"),
        ):
            cs_id = build_combined_summary_task.run([d1.id, d2.id], self.user.id, "")

        cs = CombinedSummary.objects.get(pk=cs_id)
        self.assertEqual(cs.title, "AI Generated Title")

    def test_build_combined_summary_task_needs_two_docs(self):
        from documents.tasks import build_combined_summary_task

        d1 = self._make_doc("solo.txt")
        result = build_combined_summary_task.run([d1.id], self.user.id, "")
        self.assertIsNone(result)
        self.assertEqual(CombinedSummary.objects.count(), 0)
