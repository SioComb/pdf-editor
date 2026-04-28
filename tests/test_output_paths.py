import tempfile
import unittest
from pathlib import Path

from src.output_paths import normalize_pdf_output_path, unique_path


class OutputPathTests(unittest.TestCase):
    def test_unique_path_returns_original_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "sample.pdf"

            self.assertEqual(unique_path(target), target)

    def test_unique_path_adds_numeric_suffix_when_file_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "sample.pdf"
            target.write_bytes(b"existing")

            self.assertEqual(unique_path(target), tmp_path / "sample_1.pdf")

    def test_unique_path_skips_existing_suffixes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "sample.pdf").write_bytes(b"existing")
            (tmp_path / "sample_1.pdf").write_bytes(b"existing")

            self.assertEqual(unique_path(tmp_path / "sample.pdf"), tmp_path / "sample_2.pdf")

    def test_normalize_pdf_output_path_adds_extension_and_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = normalize_pdf_output_path(tmp_path / "nested" / "merged")

            self.assertEqual(target, tmp_path / "nested" / "merged.pdf")
            self.assertTrue(target.parent.is_dir())


if __name__ == "__main__":
    unittest.main()
