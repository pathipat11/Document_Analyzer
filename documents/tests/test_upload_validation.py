from django.test import SimpleTestCase, override_settings

from documents.services.upload.upload_validation import validate_files, get_limits


class FakeFile:
    """Minimal stand-in for an UploadedFile (only .name and .size are used)."""

    def __init__(self, name: str, size: int):
        self.name = name
        self.size = size


@override_settings(
    MAX_FILES_PER_UPLOAD=3,
    MAX_UPLOAD_SIZE=1000,
    MAX_TOTAL_UPLOAD_SIZE=2000,
    ALLOWED_EXTENSIONS={"txt", "csv", "pdf", "docx"},
)
class ValidateFilesTests(SimpleTestCase):
    def test_no_files_raises(self):
        with self.assertRaises(ValueError):
            validate_files([])

    def test_valid_single_file_passes(self):
        # Should not raise.
        validate_files([FakeFile("report.pdf", 500)])

    def test_too_many_files(self):
        files = [FakeFile(f"f{i}.txt", 10) for i in range(4)]
        with self.assertRaisesMessage(ValueError, "Too many files"):
            validate_files(files)

    def test_file_over_per_file_limit(self):
        with self.assertRaisesMessage(ValueError, "too large"):
            validate_files([FakeFile("big.pdf", 1001)])

    def test_total_size_over_limit(self):
        # Each file under the per-file limit, but the sum exceeds the total.
        files = [FakeFile("a.txt", 900), FakeFile("b.txt", 900), FakeFile("c.txt", 900)]
        with self.assertRaisesMessage(ValueError, "Total upload size"):
            validate_files(files)

    def test_unsupported_extension(self):
        with self.assertRaisesMessage(ValueError, "Unsupported file type"):
            validate_files([FakeFile("malware.exe", 100)])

    def test_extension_is_case_insensitive(self):
        # Upper-case extension should still be accepted.
        validate_files([FakeFile("REPORT.PDF", 100)])


class GetLimitsTests(SimpleTestCase):
    @override_settings(
        MAX_FILES_PER_UPLOAD=7,
        MAX_UPLOAD_SIZE=123,
        MAX_TOTAL_UPLOAD_SIZE=456,
        ALLOWED_EXTENSIONS={"txt"},
    )
    def test_reads_from_settings(self):
        limits = get_limits()
        self.assertEqual(limits.max_files, 7)
        self.assertEqual(limits.max_file_size, 123)
        self.assertEqual(limits.max_total_size, 456)
        self.assertEqual(limits.allowed_exts, {"txt"})
