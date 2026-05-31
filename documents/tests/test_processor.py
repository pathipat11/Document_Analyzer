from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from documents.models import Document, DocumentChunk
from documents.services.pipeline.processor import process_document, sanitize_text

User = get_user_model()

# Use in-memory storage so tests never touch S3, and disable file relocation
# (the type-folder move) by pointing default storage at the in-memory backend.
INMEMORY_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


class SanitizeTextTests(TestCase):
    def test_removes_null_bytes(self):
        self.assertEqual(sanitize_text("a\x00b"), "ab")

    def test_normalizes_newlines(self):
        self.assertEqual(sanitize_text("a\r\nb\rc"), "a\nb\nc")

    def test_empty(self):
        self.assertEqual(sanitize_text(""), "")
        self.assertEqual(sanitize_text(None), "")


@override_settings(STORAGES=INMEMORY_STORAGES, ENABLE_LLM=False)
class ProcessDocumentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="proc", password="pw")

    def _make_doc(self, content: str, name="sample.txt", ext="txt") -> Document:
        doc = Document.objects.create(
            owner=self.user,
            file_name=name,
            file_ext=ext,
        )
        doc.file.save(name, ContentFile(content.encode("utf-8")), save=True)
        return doc

    def test_processing_sets_status_and_counts(self):
        doc = self._make_doc("hello world from the analyzer")
        process_document(doc)
        doc.refresh_from_db()
        self.assertEqual(doc.status, "done")
        self.assertEqual(doc.word_count, 5)
        self.assertGreater(doc.char_count, 0)
        self.assertIsNotNone(doc.processed_at)

    def test_chunks_are_created(self):
        doc = self._make_doc("paragraph one. " * 200)
        process_document(doc)
        self.assertTrue(DocumentChunk.objects.filter(document=doc).exists())

    def test_reprocessing_replaces_chunks(self):
        doc = self._make_doc("first version of the content here")
        process_document(doc)
        first_count = DocumentChunk.objects.filter(document=doc).count()
        self.assertGreaterEqual(first_count, 1)

        # Re-run; chunks should be rebuilt, not duplicated.
        process_document(doc)
        second_count = DocumentChunk.objects.filter(document=doc).count()
        self.assertEqual(first_count, second_count)

    def test_llm_disabled_leaves_summary_empty(self):
        doc = self._make_doc("some content without llm")
        process_document(doc)
        doc.refresh_from_db()
        self.assertEqual(doc.summary, "")
        self.assertEqual(doc.document_type, "other")
