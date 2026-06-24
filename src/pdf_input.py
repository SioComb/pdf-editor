"""Validation helpers for PDF input paths."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable


class PdfInputIssueKind(str, Enum):
    """Reason why an input path was rejected."""

    MULTIPLE_NOT_ALLOWED = "multiple_not_allowed"
    NOT_PDF = "not_pdf"
    NOT_FOUND = "not_found"
    NOT_FILE = "not_file"
    NOT_READABLE = "not_readable"
    DUPLICATE = "duplicate"


@dataclass(frozen=True)
class PdfInputIssue:
    """One rejected input path and its user-facing message."""

    kind: PdfInputIssueKind
    path: Path | None
    message: str


@dataclass(frozen=True)
class PdfInputValidationResult:
    """Accepted paths and non-fatal validation issues."""

    accepted: tuple[Path, ...]
    issues: tuple[PdfInputIssue, ...]


def canonical_path_key(path: str | Path) -> str:
    """Return a platform-aware key used to detect duplicate paths."""

    resolved = Path(path).expanduser().resolve(strict=False)
    return os.path.normcase(str(resolved))


def validate_pdf_paths(
    paths: Iterable[str | Path],
    *,
    existing: Iterable[str | Path] = (),
    allow_multiple: bool,
) -> PdfInputValidationResult:
    """Validate PDF paths without raising for normal user input errors."""

    candidates = [
        Path(path).expanduser() for path in paths if str(path).strip()
    ]
    if not allow_multiple and len(candidates) > 1:
        return PdfInputValidationResult(
            accepted=(),
            issues=(
                PdfInputIssue(
                    kind=PdfInputIssueKind.MULTIPLE_NOT_ALLOWED,
                    path=None,
                    message="この入力欄にはPDFを1件だけ指定してください。",
                ),
            ),
        )

    seen = {canonical_path_key(path) for path in existing}
    accepted: list[Path] = []
    issues: list[PdfInputIssue] = []

    for candidate in candidates:
        path = candidate.resolve(strict=False)
        if path.suffix.lower() != ".pdf":
            issues.append(
                PdfInputIssue(
                    kind=PdfInputIssueKind.NOT_PDF,
                    path=path,
                    message=f"PDF以外のファイルを無視しました: {path.name}",
                )
            )
            continue
        if not path.exists():
            issues.append(
                PdfInputIssue(
                    kind=PdfInputIssueKind.NOT_FOUND,
                    path=path,
                    message=f"ファイルが見つかりません: {path}",
                )
            )
            continue
        if not path.is_file():
            issues.append(
                PdfInputIssue(
                    kind=PdfInputIssueKind.NOT_FILE,
                    path=path,
                    message=f"ファイルではないパスを無視しました: {path}",
                )
            )
            continue
        if not _is_readable(path):
            issues.append(
                PdfInputIssue(
                    kind=PdfInputIssueKind.NOT_READABLE,
                    path=path,
                    message=f"ファイルを読み取れません: {path}",
                )
            )
            continue

        key = canonical_path_key(path)
        if key in seen:
            issues.append(
                PdfInputIssue(
                    kind=PdfInputIssueKind.DUPLICATE,
                    path=path,
                    message=f"同じファイルは追加済みです: {path.name}",
                )
            )
            continue

        accepted.append(path)
        seen.add(key)

    return PdfInputValidationResult(tuple(accepted), tuple(issues))


def _is_readable(path: Path) -> bool:
    """Check actual read access instead of relying only on permission bits."""

    try:
        with path.open("rb") as stream:
            stream.read(1)
    except OSError:
        return False
    return True
