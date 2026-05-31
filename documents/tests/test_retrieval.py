from django.contrib.auth import get_user_model
from django.test import TestCase

from documents.models import Document, DocumentChunk
from documents.services.pipeline.retrieval import retrieve_top_chunks

User = get_user_model()


class RetrieveTopChunksTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="ret", password="pw")
        cls.doc = Document.objects.create(
            owner=cls.user,
            file_name="doc.txt",
            file_ext="txt",
        )
        contents = [
            "The annual financial report covers revenue and profit growth.",
            "Cats and dogs are common household pets around the world.",
            "Revenue increased sharply due to strong product sales.",
            "This paragraph talks about gardening and growing tomatoes.",
        ]
        DocumentChunk.objects.bulk_create([
            DocumentChunk(document=cls.doc, idx=i + 1, content=c)
            for i, c in enumerate(contents)
        ])

    def test_returns_relevant_chunks_first(self):
        results = retrieve_top_chunks(self.doc.id, "revenue growth", k=2)
        self.assertTrue(results)
        # Top result should mention revenue.
        self.assertIn("revenue", results[0].content.lower())

    def test_respects_k_limit(self):
        results = retrieve_top_chunks(self.doc.id, "revenue product sales report", k=1)
        self.assertEqual(len(results), 1)

    def test_no_overlap_returns_empty(self):
        results = retrieve_top_chunks(self.doc.id, "quantum astrophysics neutrino", k=5)
        self.assertEqual(results, [])

    def test_empty_query_returns_empty(self):
        self.assertEqual(retrieve_top_chunks(self.doc.id, "", k=5), [])

    def test_scores_are_descending(self):
        results = retrieve_top_chunks(self.doc.id, "revenue product sales", k=5)
        scores = [r.score for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))
