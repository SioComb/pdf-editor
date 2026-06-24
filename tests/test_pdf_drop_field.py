import tempfile
import unittest
from pathlib import Path
from typing import Any, cast

import flet as ft

from src.gui.pdf_drop_field import PdfDropField


class FakeFilePicker:
    def __init__(self, files: list[ft.FilePickerFile] | None = None) -> None:
        self.files = files or []
        self.last_options: dict[str, Any] = {}

    async def pick_files(self, **kwargs: Any) -> list[ft.FilePickerFile]:
        self.last_options = kwargs
        return self.files


class PdfDropFieldTests(unittest.IsolatedAsyncioTestCase):
    async def test_picker_and_direct_input_share_the_same_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "日本語 file.PDF"
            path.write_bytes(b"%PDF-1.4")
            picker = FakeFilePicker(
                [
                    ft.FilePickerFile(
                        id=1,
                        name=path.name,
                        size=path.stat().st_size,
                        path=str(path),
                    )
                ]
            )
            changes: list[list[Path]] = []
            field = PdfDropField(
                file_picker=picker,
                allow_multiple=False,
                on_files_changed=lambda files: changes.append(files),
                log=lambda message: None,
            )

            await field._pick_files(cast(ft.Event, None))

            self.assertEqual(field.files, [path.resolve()])
            self.assertEqual(changes, [[path.resolve()]])
            self.assertFalse(picker.last_options["allow_multiple"])
            self.assertEqual(
                picker.last_options["file_type"],
                ft.FilePickerFileType.CUSTOM,
            )

    async def test_instances_do_not_share_state_and_clear_stays_in_sync(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "one.pdf"
            path.write_bytes(b"%PDF-1.4")
            first_changes: list[list[Path]] = []
            second_changes: list[list[Path]] = []
            first = PdfDropField(
                file_picker=FakeFilePicker(),
                allow_multiple=True,
                on_files_changed=lambda files: first_changes.append(files),
                log=lambda message: None,
            )
            second = PdfDropField(
                file_picker=FakeFilePicker(),
                allow_multiple=True,
                on_files_changed=lambda files: second_changes.append(files),
                log=lambda message: None,
            )

            await first.add_paths([path], source="test")

            self.assertEqual(first.files, [path.resolve()])
            self.assertEqual(second.files, [])
            await first.clear()
            self.assertEqual(first.files, [])
            self.assertEqual(first_changes[-1], [])
            self.assertEqual(second_changes, [])


if __name__ == "__main__":
    unittest.main()
