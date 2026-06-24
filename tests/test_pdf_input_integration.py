import tempfile
import unittest
from pathlib import Path

import flet as ft
from pypdf import PdfWriter

from src.gui.app import pdf_marge, pdf_split, pdf_to_image
from src.gui.pdf_drop_field import PdfDropField

def _write_pdf(path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with path.open("wb") as stream:
        writer.write(stream)


class PdfInputIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_component_paths_drive_all_pdf_processors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "日本語 first.PDF"
            second = root / "second.pdf"
            output = root / "output"
            _write_pdf(first)
            _write_pdf(second)

            single = PdfDropField(
                file_picker=ft.FilePicker(),
                allow_multiple=False,
                on_files_changed=lambda files: None,
                log=lambda message: None,
            )
            await single.add_paths([first], source="test")

            image_result = await pdf_to_image(
                single.value,
                "file",
                str(output / "images"),
                "png",
                72,
            )
            split_result = await pdf_split(
                single.value,
                "all",
                "",
                str(output / "split"),
            )

            multiple = PdfDropField(
                file_picker=ft.FilePicker(),
                allow_multiple=True,
                on_files_changed=lambda files: None,
                log=lambda message: None,
            )
            await multiple.add_paths([first, second], source="test")
            merged = await pdf_marge(
                "files",
                multiple.paths,
                "",
                str(output / "merged.pdf"),
            )

            self.assertTrue(Path(image_result["files"][0]).is_file())
            self.assertTrue(Path(split_result[0]).is_file())
            self.assertTrue(Path(merged).is_file())


if __name__ == "__main__":
    unittest.main()
