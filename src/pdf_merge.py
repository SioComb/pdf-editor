"""PDF merging module using pypdf."""

from pathlib import Path
from threading import Event

from pypdf import PdfWriter

from src.output_paths import normalize_pdf_output_path


def _pdf_files_in_dir(input_dir: Path) -> list[Path]:
    return sorted(
        (p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"),
        key=lambda p: p.name.lower(),
    )


def _raise_if_cancelled(cancel_event: Event | None) -> None:
    if cancel_event and cancel_event.is_set():
        raise InterruptedError("Operation cancelled")


def merge_pdfs(
    pdf_paths: list[str],
    output_path: str,
    *,
    auto_rename: bool = True,
    cancel_event: Event | None = None,
) -> str:
    """Merge multiple PDF files into a single output file.

    Args:
        pdf_paths: Ordered list of paths to input PDF files.
        output_path: Full path (including filename) for the merged PDF.

    Returns:
        Absolute path to the merged PDF file.
    """
    output_path = normalize_pdf_output_path(output_path, auto_rename=auto_rename)

    writer = PdfWriter()
    for path in pdf_paths:
        _raise_if_cancelled(cancel_event)
        writer.append(str(path))

    _raise_if_cancelled(cancel_event)
    with open(output_path, "wb") as f:
        writer.write(f)

    return str(output_path)


def merge_folder(
    input_dir: str,
    output_path: str,
    *,
    auto_rename: bool = True,
    cancel_event: Event | None = None,
) -> str:
    """Merge all PDF files found in a directory into a single output file.

    Files are merged in alphabetical order of their filenames.

    Args:
        input_dir: Directory containing PDF files to merge.
        output_path: Full path (including filename) for the merged PDF.

    Returns:
        Absolute path to the merged PDF file.
    """
    input_dir = Path(input_dir)
    pdf_files = _pdf_files_in_dir(input_dir)

    if not pdf_files:
        raise FileNotFoundError(f"No PDF files found in: {input_dir}")

    return merge_pdfs(
        [str(p) for p in pdf_files],
        output_path,
        auto_rename=auto_rename,
        cancel_event=cancel_event,
    )
