"""Reusable PDF input field for Flet tabs."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Awaitable, Callable, Iterable, Protocol

import flet as ft

from src.pdf_input import PdfInputIssue, PdfInputIssueKind, validate_pdf_paths
from src.pdf_input import canonical_path_key


FilesChangedCallback = Callable[[list[Path]], Awaitable[None] | None]
LogCallback = Callable[[str], None]


class PdfFilePicker(Protocol):
    """Subset of ``ft.FilePicker`` used by ``PdfDropField``."""

    async def pick_files(
        self,
        *,
        dialog_title: str | None = None,
        file_type: ft.FilePickerFileType = ft.FilePickerFileType.ANY,
        allowed_extensions: list[str] | None = None,
        allow_multiple: bool = False,
    ) -> list[ft.FilePickerFile]: ...


class PdfDropField(ft.Column):
    """Validated PDF picker with an independent per-instance file list.

    Flet 0.85.1 does not expose operating-system file-drop events. The drop-zone
    appearance is therefore a click target backed by the official ``FilePicker``
    service. ``add_paths`` is the single state path used by the picker and by a
    future native drop adapter.
    """

    def __init__(
        self,
        *,
        file_picker: PdfFilePicker,
        allow_multiple: bool,
        on_files_changed: FilesChangedCallback,
        log: LogCallback,
        select_button_text: str = "ファイルを選択",
    ) -> None:
        super().__init__(spacing=8)
        self._file_picker = file_picker
        self._allow_multiple = allow_multiple
        self._on_files_changed = on_files_changed
        self._log = log
        self._files: list[Path] = []

        self._status_text = ft.Text(
            "Flet 0.85.1ではOSからのファイルドロップは未対応です。",
            size=11,
            color=ft.Colors.BLUE_GREY_600,
            text_align=ft.TextAlign.CENTER,
        )
        self._error_text = ft.Text(
            color=ft.Colors.RED_700,
            size=12,
            visible=False,
        )
        self._drop_area = ft.Container(
            height=126,
            padding=16,
            alignment=ft.Alignment.CENTER,
            border=ft.Border.all(2, ft.Colors.BLUE_GREY_300),
            border_radius=10,
            bgcolor=ft.Colors.BLUE_GREY_50,
            animate=150,
            ink=True,
            on_click=self._pick_files,
            on_hover=self._handle_hover,
            content=ft.Column(
                [
                    ft.Icon(
                        ft.Icons.UPLOAD_FILE,
                        size=34,
                        color=ft.Colors.RED_500,
                    ),
                    ft.Text(
                        "ここにPDFファイルをドラッグ＆ドロップ\n"
                        "またはクリックしてファイルを選択",
                        text_align=ft.TextAlign.CENTER,
                        weight=ft.FontWeight.BOLD,
                    ),
                    self._status_text,
                ],
                tight=True,
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
        )
        self._file_list = ft.Column(spacing=4)
        self._clear_button = ft.TextButton(
            "全件クリア",
            icon=ft.Icons.CLEAR_ALL,
            on_click=self._clear_clicked,
            visible=False,
        )
        self._select_button = ft.Button(
            content=select_button_text,
            icon=ft.Icons.FOLDER_OPEN,
            on_click=self._pick_files,
        )
        self.controls = [
            self._drop_area,
            self._error_text,
            ft.Row(
                [self._select_button, self._clear_button],
                spacing=8,
            ),
            self._file_list,
        ]

    @property
    def files(self) -> list[Path]:
        """Return a copy of the accepted files in display order."""

        return list(self._files)

    @property
    def paths(self) -> list[str]:
        """Return accepted paths in the format used by PDF processors."""

        return [str(path) for path in self._files]

    @property
    def value(self) -> str:
        """Return one path, or an empty string when none is selected."""

        return str(self._files[0]) if self._files else ""

    async def add_paths(
        self,
        paths: Iterable[str | Path],
        *,
        source: str,
        notify: bool = True,
    ) -> None:
        """Validate and add paths through the component's single state path."""

        candidates = list(paths)
        existing = self._files if self._allow_multiple else []
        if (
            not self._allow_multiple
            and len(candidates) == 1
            and self._files
            and canonical_path_key(candidates[0])
            == canonical_path_key(self._files[0])
        ):
            existing = self._files
        result = validate_pdf_paths(
            candidates,
            existing=existing,
            allow_multiple=self._allow_multiple,
        )

        if self._allow_multiple:
            self._files.extend(result.accepted)
        elif result.accepted:
            old_files = self._files
            self._files = [result.accepted[0]]
            for old_path in old_files:
                if old_path != self._files[0]:
                    self._log(f"ℹ PDFを再選択しました: {old_path.name}")

        for path in result.accepted:
            self._log(f"✓ PDFを追加しました（{source}）: {path}")
        self._report_issues(result.issues)
        self._refresh()
        if notify and result.accepted:
            await self._notify_changed()

    async def clear(self, *, notify: bool = True) -> None:
        """Remove all files and keep UI and state synchronized."""

        if not self._files:
            return
        removed = list(self._files)
        self._files.clear()
        for path in removed:
            self._log(f"✓ PDFを削除しました: {path}")
        self._error_text.visible = False
        self._refresh()
        if notify:
            await self._notify_changed()

    async def _pick_files(self, e: ft.Event) -> None:
        try:
            selected = await self._file_picker.pick_files(
                dialog_title="PDFファイルを選択",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["pdf", "PDF"],
                allow_multiple=self._allow_multiple,
            )
            missing_paths = [item.name for item in selected if not item.path]
            if missing_paths:
                message = "ファイルのローカルパスを取得できませんでした。"
                self._show_error(message)
                self._log(f"⚠ {message}: {', '.join(missing_paths)}")
            await self.add_paths(
                [item.path for item in selected if item.path],
                source="ファイル選択",
            )
        except Exception as exc:
            self._show_error("ファイル選択中にエラーが発生しました。")
            self._log(f"✗ ファイル選択処理で例外が発生しました: {exc}")
            self._safe_update()

    async def _remove_clicked(self, e: ft.Event) -> None:
        path = Path(str(e.control.data))
        for index, current in enumerate(self._files):
            if current == path:
                removed = self._files.pop(index)
                self._log(f"✓ PDFを削除しました: {removed}")
                self._refresh()
                await self._notify_changed()
                return

    async def _clear_clicked(self, e: ft.Event) -> None:
        await self.clear()

    def _handle_hover(self, e: ft.Event) -> None:
        active = str(e.data).lower() == "true"
        self._drop_area.border = ft.Border.all(
            2,
            ft.Colors.BLUE_500 if active else ft.Colors.BLUE_GREY_300,
        )
        self._drop_area.bgcolor = (
            ft.Colors.BLUE_50 if active else ft.Colors.BLUE_GREY_50
        )
        self._safe_update(self._drop_area)

    def _refresh(self) -> None:
        self._file_list.controls = [
            self._build_file_row(path) for path in self._files
        ]
        self._clear_button.visible = bool(self._files)
        count = len(self._files)
        self._status_text.value = (
            f"{count}件のPDFを受け付けました"
            if count
            else "Flet 0.85.1ではOSからのファイルドロップは未対応です。"
        )
        self._safe_update()

    def _build_file_row(self, path: Path) -> ft.Control:
        try:
            size = _format_size(path.stat().st_size)
        except OSError:
            size = "サイズ取得不可"
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=6),
            border=ft.Border.all(1, ft.Colors.BLUE_GREY_200),
            border_radius=6,
            content=ft.Row(
                [
                    ft.Icon(
                        ft.Icons.PICTURE_AS_PDF,
                        color=ft.Colors.RED_500,
                    ),
                    ft.Column(
                        [
                            ft.Text(
                                path.name,
                                weight=ft.FontWeight.BOLD,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            ft.Text(
                                f"{path}  ({size})",
                                size=11,
                                color=ft.Colors.BLUE_GREY_700,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                tooltip=str(path),
                            ),
                        ],
                        expand=True,
                        spacing=1,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.REMOVE_CIRCLE_OUTLINE,
                        icon_color=ft.Colors.RED_400,
                        tooltip="一覧から削除",
                        data=str(path),
                        on_click=self._remove_clicked,
                    ),
                ]
            ),
        )

    def _report_issues(self, issues: tuple[PdfInputIssue, ...]) -> None:
        if not issues:
            self._error_text.visible = False
            return
        self._show_error("\n".join(issue.message for issue in issues))
        for issue in issues:
            label = {
                PdfInputIssueKind.DUPLICATE: "重複ファイル",
                PdfInputIssueKind.NOT_PDF: "PDF以外",
                PdfInputIssueKind.NOT_FOUND: "存在しないファイル",
                PdfInputIssueKind.NOT_FILE: "ファイルではないパス",
                PdfInputIssueKind.NOT_READABLE: "読み取り不可",
                PdfInputIssueKind.MULTIPLE_NOT_ALLOWED: "複数指定",
            }[issue.kind]
            self._log(f"⚠ {label}: {issue.message}")

    def _show_error(self, message: str) -> None:
        self._error_text.value = message
        self._error_text.visible = True

    async def _notify_changed(self) -> None:
        result = self._on_files_changed(self.files)
        if inspect.isawaitable(result):
            await result

    def _safe_update(self, control: ft.Control | None = None) -> None:
        target = control or self
        try:
            target.update()
        except RuntimeError as exc:
            if "must be added to the page first" not in str(exc):
                raise


def _format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return f"{value:.0f} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"
