import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.pdf_input import PdfInputIssueKind, validate_pdf_paths


class PdfInputValidationTests(unittest.TestCase):
    def test_accepts_pdf_extensions_case_insensitively(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = [root / "sample.pdf", root / "日本語 ファイル.PDF"]
            for path in paths:
                path.write_bytes(b"%PDF-1.4")

            result = validate_pdf_paths(paths, allow_multiple=True)

            self.assertEqual(
                result.accepted,
                tuple(path.resolve() for path in paths),
            )
            self.assertEqual(result.issues, ())

    def test_rejects_non_pdf_and_missing_files_without_stopping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            valid = root / "valid.pdf"
            invalid = root / "notes.txt"
            missing = root / "missing.pdf"
            valid.write_bytes(b"%PDF-1.4")
            invalid.write_text("not a pdf", encoding="utf-8")

            result = validate_pdf_paths(
                [invalid, valid, missing],
                allow_multiple=True,
            )

            self.assertEqual(result.accepted, (valid.resolve(),))
            self.assertEqual(
                {issue.kind for issue in result.issues},
                {PdfInputIssueKind.NOT_PDF, PdfInputIssueKind.NOT_FOUND},
            )

    def test_rejects_duplicates_in_existing_and_same_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first.pdf"
            second = root / "second.pdf"
            first.write_bytes(b"%PDF-1.4")
            second.write_bytes(b"%PDF-1.4")

            result = validate_pdf_paths(
                [first, second, second],
                existing=[first],
                allow_multiple=True,
            )

            self.assertEqual(result.accepted, (second.resolve(),))
            self.assertEqual(
                [issue.kind for issue in result.issues],
                [PdfInputIssueKind.DUPLICATE, PdfInputIssueKind.DUPLICATE],
            )

    def test_rejects_entire_multi_file_input_for_single_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = [root / "one.pdf", root / "two.pdf"]
            for path in paths:
                path.write_bytes(b"%PDF-1.4")

            result = validate_pdf_paths(paths, allow_multiple=False)

            self.assertEqual(result.accepted, ())
            self.assertEqual(len(result.issues), 1)
            self.assertEqual(
                result.issues[0].kind,
                PdfInputIssueKind.MULTIPLE_NOT_ALLOWED,
            )

    def test_rejects_unreadable_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "locked.pdf"
            path.write_bytes(b"%PDF-1.4")

            with patch("src.pdf_input._is_readable", return_value=False):
                result = validate_pdf_paths([path], allow_multiple=False)

            self.assertEqual(result.accepted, ())
            self.assertEqual(
                result.issues[0].kind,
                PdfInputIssueKind.NOT_READABLE,
            )


if __name__ == "__main__":
    unittest.main()
