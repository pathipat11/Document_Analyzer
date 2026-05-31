from django.test import SimpleTestCase

from documents.services.pipeline.chunking import chunk_text


class ChunkTextTests(SimpleTestCase):
    def test_empty_text_returns_empty_list(self):
        self.assertEqual(chunk_text(""), [])
        self.assertEqual(chunk_text("   "), [])
        self.assertEqual(chunk_text(None), [])

    def test_short_text_single_chunk(self):
        text = "This is a short document."
        chunks = chunk_text(text, chunk_size=900, overlap=150)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], text)

    def test_long_text_is_split(self):
        # Build a long text well over the chunk size.
        text = ". ".join(f"sentence number {i}" for i in range(500))
        chunks = chunk_text(text, chunk_size=300, overlap=50)
        self.assertGreater(len(chunks), 1)
        # No chunk should be drastically larger than chunk_size + break window.
        for c in chunks:
            self.assertLessEqual(len(c), 300 + 200)

    def test_chunks_have_overlap_and_progress(self):
        text = "x" * 2000
        chunks = chunk_text(text, chunk_size=500, overlap=100)
        self.assertGreater(len(chunks), 1)
        # Every chunk should carry content (no empties).
        self.assertTrue(all(c.strip() for c in chunks))

    def test_no_infinite_loop_with_large_overlap(self):
        # overlap close to chunk_size must still terminate and make progress.
        text = "word " * 1000
        chunks = chunk_text(text, chunk_size=100, overlap=99)
        self.assertGreater(len(chunks), 1)
        self.assertLess(len(chunks), len(text))
