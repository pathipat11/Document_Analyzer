import csv
import io

from django.test import SimpleTestCase

from documents.services.pipeline.text_extractor import extract_text_bytes


class ExtractTextBytesTests(SimpleTestCase):
    def test_txt_utf8(self):
        res = extract_text_bytes("hello world".encode("utf-8"), "txt")
        self.assertEqual(res.text, "hello world")
        self.assertEqual(res.word_count, 2)
        self.assertEqual(res.char_count, len("hello world"))

    def test_txt_thai(self):
        text = "สวัสดี ชาวโลก"
        res = extract_text_bytes(text.encode("utf-8"), "txt")
        self.assertEqual(res.text, text)
        self.assertEqual(res.word_count, 2)

    def test_txt_invalid_bytes_does_not_crash(self):
        # Invalid UTF-8 should be decoded with errors ignored, not raise.
        res = extract_text_bytes(b"\xff\xfe valid", "txt")
        self.assertIn("valid", res.text)

    def test_csv_is_flattened(self):
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["name", "age"])
        writer.writerow(["alice", "30"])
        res = extract_text_bytes(buf.getvalue().encode("utf-8"), "csv")
        self.assertIn("name, age", res.text)
        self.assertIn("alice, 30", res.text)

    def test_unknown_extension_falls_back_to_text(self):
        res = extract_text_bytes("plain content".encode("utf-8"), "unknown")
        self.assertEqual(res.text, "plain content")

    def test_empty_bytes(self):
        res = extract_text_bytes(b"", "txt")
        self.assertEqual(res.text, "")
        self.assertEqual(res.word_count, 0)
        self.assertEqual(res.char_count, 0)
