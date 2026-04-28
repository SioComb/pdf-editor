"""Output path helpers for generated files."""

from pathlib import Path


def unique_path(path: str | Path) -> Path:
    """Return a non-existing path by appending a numeric suffix when needed."""
    candidate = Path(path)
    if not candidate.exists():
        return candidate

    parent = candidate.parent
    stem = candidate.stem
    suffix = candidate.suffix
    index = 1
    while True:
        renamed = parent / f"{stem}_{index}{suffix}"
        if not renamed.exists():
            return renamed
        index += 1


def normalize_pdf_output_path(path: str | Path, *, auto_rename: bool = True) -> Path:
    """Normalize a PDF output path and optionally avoid overwriting files."""
    output_path = Path(path)
    if output_path.suffix.lower() != ".pdf":
        output_path = output_path.with_suffix(".pdf")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return unique_path(output_path) if auto_rename else output_path
