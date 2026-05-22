"""Small platform-specific helpers."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# フォルダを開く
def open_folder(path: str | Path) -> None:
    """Open a folder with the platform's default file manager."""
    folder = str(Path(path))
    if sys.platform.startswith("win"):
        os.startfile(folder)  # type: ignore[attr-defined]
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", folder]) # 機能していない？
        return
    subprocess.Popen(["xdg-open", folder])
