import asyncio
import tempfile
import unittest
from pathlib import Path
from typing import Any

import flet as ft

from src.gui.app import build_convert_tab, build_merge_tab, build_split_tab


class GuiBuildTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_pdf_input_tabs_build_independently(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            preferences: dict[str, Any] = {}

            async def pref_get(key: str, default: Any) -> Any:
                return preferences.get(key, default)

            async def pref_set(key: str, value: Any) -> None:
                preferences[key] = value

            async def choose_dir() -> str | None:
                return None

            async def run_in_thread(function: Any, *args: Any) -> Any:
                return await asyncio.to_thread(function, *args)

            async def show_busy(*args: Any) -> None:
                return None

            common = {
                "pref_get": pref_get,
                "pref_set": pref_set,
                "file_picker": ft.FilePicker(),
                "choose_dir_async": choose_dir,
                "run_in_thread": run_in_thread,
                "log": lambda message: None,
                "show_busy": show_busy,
                "hide_busy": lambda: None,
                "default_output_dir": str(Path(tmp) / "output"),
            }

            convert = await build_convert_tab(**common)
            split = await build_split_tab(**common)
            merge = await build_merge_tab(**common)

            self.assertIsInstance(convert, ft.Container)
            self.assertIsInstance(split, ft.Container)
            self.assertIsInstance(merge, ft.Container)
            self.assertIsNot(convert, split)
            self.assertIsNot(split, merge)


if __name__ == "__main__":
    unittest.main()
