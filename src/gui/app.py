# coding: utf-8
# app.py - PDF Editor GUI
# Python 3.12 / Flet 0.85.1



from __future__ import annotations

import asyncio
from threading import Event
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional, cast

import flet as ft

from src.pdf_merge import merge_folder, merge_pdfs
from src.pdf_split import split_by_range, split_pdf
from src.pdf_to_img import convert_folder, pdf_to_images
from src.platform_utils import open_folder


APP_NAME = "PDF Editor"
BASE_DIR = Path(__file__).resolve().parents[2]
INPUT_DIR = BASE_DIR / "input"
DEFAULT_OUTPUT_DIR = BASE_DIR / "output"

PREF_PREFIX = "panasss.pdf_editor."  # unique prefix for shared_preferences keys

# 画面の解像度が高い場合のウィンドウサイズ調整（例: 4K など）
def adhust_sindow_size(page: ft.Page):
    # 画面サイズと DPI を元にウィンドウサイズを動的に決定する
    try:
        sw = getattr(page.window, "screen_width", None)
        sh = getattr(page.window, "screen_height", None)
        dpr = getattr(page.window, "device_pixel_ratio", 1) or 1
        if sw is None or sh is None:
            return
        # 論理ピクセルに変換（高DPI時の補正）
        logical_w = int(sw / dpr)
        logical_h = int(sh / dpr)
        # 幅・高さは画面割合で決め、最小値・余白を確保
        w = max(800, int(logical_w * 0.6))
        h = max(600, int(logical_h * 0.6))
        # 画面全部を覆わないようマージンを確保
        w = min(w, logical_w - 200)
        h = min(h, logical_h - 150)
        page.window.width = w
        page.window.height = h
    except Exception:
        # 安全策: 何か失敗しても固定サイズが使われるようにする
        pass

# ── tkinter ダイアログ（FilePicker は使用しない） ──────────────────────────────
def _tk_choose_file(multiple: bool = False):
    # モジュール（グローバル） — GUI から呼ばれるファイル選択ダイアログヘルパー
    # 目的: tkinter を使ってユーザーにファイルを選ばせる。GUI スレッド外からも呼ばれる。
    try:
        import tkinter as _tk
        from tkinter import filedialog as _fd

        root = _tk.Tk()
        root.title("ファイルを選択してください。")
        root.attributes("-topmost", True)  # ダイアログを最前面に表示
        root.withdraw()
        if multiple:
            res = list(_fd.askopenfilenames(filetypes=[("PDF files", "*.pdf"), ("All files", "*")]))
        else:
            res = _fd.askopenfilename(filetypes=[("PDF files", "*.pdf"), ("All files", "*")])
        root.destroy()
        return res if res else None
    except Exception:
        return None


def _tk_choose_dir():
    # モジュール（グローバル） — GUI から呼ばれるフォルダ選択ダイアログヘルパー
    # 目的: tkinter を使ってディレクトリを選択する。GUI スレッド外からも呼ばれる。
    try:
        import tkinter as _tk
        from tkinter import filedialog as _fd

        root = _tk.Tk()
        root.title("フォルダを選択してください。")
        root.attributes("-topmost", True)  # ダイアログを最前面に表示
        root.withdraw()
        res = _fd.askdirectory()
        root.destroy()
        return res if res else None
    except Exception:
        return None


def _is_pdf_file(path: str) -> bool:
    # モジュール（ユーティリティ） — パスが PDF ファイルかを判定する純粋関数
    p = Path(path)
    return p.is_file() and p.suffix.lower() == ".pdf"


def _ensure_dir(path: str) -> None:
    # モジュール（ユーティリティ） — 出力フォルダを作成する副作用関数
    Path(path).mkdir(parents=True, exist_ok=True)


def _open_folder_windows(path: str) -> None:
    # モジュール（プラットフォーム依存） — Windows 専用でフォルダを開く
    open_folder(path)

async def pdf_to_image(source: str, mode: str, out_dir: str, fmt: str, dpi: int, cancel_event: Event | None = None):
    """トップレベル関数 — PDF を画像に変換する処理を実行する。
    パラメータは UI 側から渡され、ブロッキングな処理は内部で `asyncio.to_thread` によって実行される。
    戻り値: ファイルリストまたはフォルダ変換の結果辞書を返す。
    """
    p = Path(source)
    
    if mode == "file":
        if not p.exists() or not p.is_file() or p.suffix.lower() != ".pdf":
            raise ValueError("正しいPDFファイルを選択してください")
        files = await asyncio.to_thread(pdf_to_images, source, out_dir, fmt, dpi, cancel_event=cancel_event)
        
        print("DEBUG: after to_thread pdf_to_images")
        
        return {"mode": "file", "files": files}
    
    else:
        print("DEBUG: pdf_to_image folder mode start")
        
        if not p.exists() or not p.is_dir():
            raise ValueError("指定されたフォルダが見つかりません")
        
        print("DEBUG: before to_thread convert_folder")
        results = await asyncio.to_thread(
            convert_folder,
            source,
            out_dir,
            fmt,
            dpi,
            cancel_event=cancel_event,
        )
        print("DEBUG: after to_thread convert_folder")
        
        return {"mode": "folder", "results": results}


async def pdf_split(source: str, mode: str, rng: str, out_dir: str, cancel_event: Event | None = None):
    """トップレベル関数 — PDF を分割する処理を実行する。
    mode: 'all' または 'range'
    戻り値: 出力ファイルリストを返す。
    """
    if not _is_pdf_file(source):
        raise ValueError("正しいPDFファイルを選択してください")
    if mode == "all":
        files = await asyncio.to_thread(split_pdf, source, out_dir, cancel_event=cancel_event)
        return files
    else:
        if not (rng and rng.strip()):
            raise ValueError("ページ範囲を入力してください")
        files = await asyncio.to_thread(split_by_range, source, out_dir, rng, cancel_event=cancel_event)
        return files


async def pdf_marge(mode: str, paths: list[str], folder_path: str, out_path: str, cancel_event: Event | None = None):
    """トップレベル関数 — PDF を結合する処理を実行する。
    mode: 'files' または 'folder'
    paths: ファイルリスト（mode=='files' のとき使用）
    folder_path: フォルダパス（mode=='folder' のとき使用）
    戻り値: 実行結果（出力パス等）を返す。
    """
    if mode == "files":
        if not paths:
            raise ValueError("PDFファイルを追加してください")
        bad = [p for p in paths if not _is_pdf_file(p)]
        if bad:
            raise ValueError("存在しないPDFが含まれています: " + ", ".join(Path(x).name for x in bad))
        result = await asyncio.to_thread(merge_pdfs, paths, out_path, cancel_event=cancel_event)
        return result
    else:
        folder = folder_path or ""
        if not folder or not Path(folder).is_dir():
            raise ValueError("正しいフォルダを選択してください")
        result = await asyncio.to_thread(merge_folder, folder, out_path, cancel_event=cancel_event)
        return result


async def build_convert_tab(
    *,
    pref_get: Callable[[str, Any], Awaitable[Any]],
    pref_set: Callable[[str, Any], Awaitable[None]],
    choose_file_async: Callable[..., Awaitable[Optional[str]]],
    choose_dir_async: Callable[[], Awaitable[Optional[str]]],
    run_in_thread: Callable[..., Awaitable[Any]],
    log: Callable[[str], None],
    show_busy: Callable[..., Awaitable[None]],
    hide_busy: Callable[[], None],
    default_output_dir: str,
):
    """コンバータタブを構築して `ft.Container` を返す。
    スコープ: モジュール内ヘルパー — main から await して呼び出す。
    """
    conv_output = OutputDirPicker(
        label="出力先フォルダ（画像）",
        default_dir=str(default_output_dir),
        pref_key="conv.output_dir",
        pref_get=pref_get,
        pref_set=pref_set,
        choose_dir_async=choose_dir_async,
        log=log,
    )
    await conv_output.load()

    conv_mode = ft.RadioGroup(
        value=cast(str, await pref_get("conv.mode", "file")),
        content=ft.Row(
            wrap=True,
            spacing=14,
            run_spacing=6,
            controls=[
                ft.Radio(value="file", label="ファイル"),
                ft.Radio(value="folder", label="フォルダ"),
            ],
        ),
    )

    conv_input = ft.TextField(label="入力PDF（ファイル/フォルダ）", hint_text="選択してください", expand=True)
    conv_input.value = cast(str, await pref_get("conv.last_source", ""))

    conv_format = ft.RadioGroup(
        value=cast(str, await pref_get("conv.format", "jpeg")),
        content=ft.Row(
            wrap=True,
            spacing=14,
            run_spacing=6,
            controls=[ft.Radio(value="jpeg", label="JPEG"), ft.Radio(value="png", label="PNG")],
        ),
    )

    async def conv_dpi_selected(e: ft.Event) -> None:
        await pref_set("conv.dpi", conv_dpi.value)

    conv_dpi = ft.Dropdown(
        label="解像度 (DPI)",
        options=[ft.dropdown.Option("100"), ft.dropdown.Option("200"), ft.dropdown.Option("300")],
        value=cast(str, await pref_get("conv.dpi", "200")),
        width=180,
        on_select=conv_dpi_selected,
    )

    conv_pick_btn = ft.Button(content="選択", width=90)
    conv_run_btn = ft.Button(
        content="変換実行",
        icon=ft.Icons.PLAY_ARROW,
        bgcolor=ft.Colors.BLUE_600,
        color=ft.Colors.WHITE,
        width=200,
    )

    async def conv_mode_changed(e: ft.Event) -> None:
        await pref_set("conv.mode", conv_mode.value)

    async def conv_format_changed(e: ft.Event) -> None:
        await pref_set("conv.format", conv_format.value)

    conv_mode.on_change = conv_mode_changed
    conv_format.on_change = conv_format_changed

    async def pick_conv_source(e: ft.Event) -> None:
        if conv_mode.value == "file":
            res = await choose_file_async(multiple=False)
        else:
            res = await choose_dir_async()
        if isinstance(res, str) and res:
            conv_input.value = res
            await pref_set("conv.last_source", res)

    async def do_convert(e: ft.Event) -> None:
        source = (conv_input.value or "").strip()
        if not source:
            log("⚠ 入力PDF（ファイル/フォルダ）を選択してください")
            return

        out_dir = conv_output.value
        if not out_dir:
            log("⚠ 出力先フォルダ（画像）を設定してください")
            return
        _ensure_dir(out_dir)

        fmt = (conv_format.value or "jpeg").lower()
        dpi = int(conv_dpi.value or "150")

        p = Path(source)
        if conv_mode.value == "file":
            if not p.exists() or not p.is_file() or p.suffix.lower() != ".pdf":
                log("⚠ 正しいPDFファイルを選択してください")
                return
        else:
            if not p.exists() or not p.is_dir():
                log("⚠ 指定されたフォルダが見つかりません")
                return

        conv_run_btn.disabled = True
        conv_pick_btn.disabled = True
        cancel_event = Event()
        try:
            await show_busy("PDF → 画像 変換中...", cancel_event)
        except Exception as e:
            log(f"⚠ show_busy failed: {e}")

        try:
            log(f"▶ 変換開始: {source}")
            log("--- worker: start pdf_to_image ---")
            res = await pdf_to_image(source, conv_mode.value, out_dir, fmt, dpi, cancel_event)
            log("--- worker: finished pdf_to_image ---")
            if res.get("mode") == "file":
                files = res.get("files", [])
                log(f"✓ 完了: {len(files)} ページ → {out_dir}")
            else:
                results = res.get("results", {})
                ok = sum(len(v) for v in results.values() if isinstance(v, list))
                ng = sum(1 for v in results.values() if isinstance(v, str))
                log(
                    f"✓ 完了: {len(results)} ファイル / {ok} ページ変換"
                    + (f" / {ng} エラー" if ng else "")
                    + f" → {out_dir}"
                )
        except InterruptedError:
            log("Cancelled.")
        except ValueError as ve:
            log(f"⚠ {ve}")
        except Exception as exc:
            log(f"✗ エラー: {exc}")
        finally:
            try:
                hide_busy()
            except Exception as e:
                log(f"⚠ hide_busy failed: {e}")
            conv_run_btn.disabled = False
            conv_pick_btn.disabled = False
            conv_run_btn.update()
            conv_pick_btn.update()

    conv_pick_btn.on_click = pick_conv_source
    conv_run_btn.on_click = do_convert

    tab_convert = ft.Container(
        padding=ft.Padding.all(16),
        content=ft.ListView(
            expand=True,
            spacing=16,
            controls=[
                ft.Text("PDF → JPEG / PNG に変換", size=18, weight=ft.FontWeight.BOLD),
                ft.Row([ft.Text("変換モード:", width=90), conv_mode]),
                ft.Row([conv_input, conv_pick_btn], spacing=8),
                ft.Row(
                    [
                        ft.Column([ft.Text("出力オプション"), conv_format], expand=True),
                        ft.Column([conv_dpi], width=200),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.END,
                ),
                conv_output,
                conv_run_btn,
            ],
        ),
    )

    return tab_convert


async def build_split_tab(
    *,
    pref_get: Callable[[str, Any], Awaitable[Any]],
    pref_set: Callable[[str, Any], Awaitable[None]],
    choose_file_async: Callable[..., Awaitable[Optional[str]]],
    choose_dir_async: Callable[[], Awaitable[Optional[str]]],
    run_in_thread: Callable[..., Awaitable[Any]],
    log: Callable[[str], None],
    show_busy: Callable[..., Awaitable[None]],
    hide_busy: Callable[[], None],
    default_output_dir: str,
):
    """分割タブを構築して `ft.Container` を返す。"""
    split_output = OutputDirPicker(
        label="出力先フォルダ（分割）",
        default_dir=str(default_output_dir),
        pref_key="split.output_dir",
        pref_get=pref_get,
        pref_set=pref_set,
        choose_dir_async=choose_dir_async,
        log=log,
    )
    await split_output.load()

    split_input = ft.TextField(label="入力PDFファイル", hint_text="PDFファイルを選択してください", expand=True)
    split_input.value = cast(str, await pref_get("split.last_source", ""))

    split_mode = ft.RadioGroup(
        value =cast(str, await pref_get("split.mode", "all")),
        content=ft.Row(
            wrap=True,
            spacing=14,
            run_spacing=6,
            controls=[
                ft.Radio(value="all", label="全ページ（1ページずつ）"),
                ft.Radio(value="range", label="ページ範囲指定"),
            ],
        ),
    )

    split_range = ft.TextField(label="ページ範囲（例: 1-3, 5, 7-9）", hint_text="カンマ区切り", expand=True)
    split_range.value = cast(str, await pref_get("split.range", ""))

    split_pick_btn = ft.Button(content="選択", width=90)
    split_run_btn = ft.Button(
        content="分割実行",
        icon=ft.Icons.PLAY_ARROW,
        bgcolor=ft.Colors.GREEN_600,
        color=ft.Colors.WHITE,
        width=200,
    )

    async def split_mode_changed(e: ft.Event) -> None:
        await pref_set("split.mode", split_mode.value)

    async def split_range_changed(e: ft.Event) -> None:
        await pref_set("split.range", split_range.value or "")

    split_mode.on_change = split_mode_changed
    split_range.on_change = split_range_changed

    async def pick_split_source(e: ft.Event) -> None:
        res = await choose_file_async(multiple=False)
        if isinstance(res, str) and res:
            split_input.value = res
            await pref_set("split.last_source", res)

    async def do_split(e: ft.Event) -> None:
        source = (split_input.value or "").strip()
        if not source or not _is_pdf_file(source):
            log("⚠ 正しいPDFファイルを選択してください")
            return

        out_dir = split_output.value
        if not out_dir:
            log("⚠ 出力先フォルダ（分割）を設定してください")
            return
        _ensure_dir(out_dir)

        split_run_btn.disabled = True
        split_pick_btn.disabled = True
        cancel_event = Event()
        try:
            await show_busy("PDF 分割中...", cancel_event)
        except Exception as e:
            log(f"⚠ show_busy failed: {e}")

        try:
            log(f"▶ 分割開始: {source}")
            log("--- worker: start split_pdf / split_by_range ---")
            files = await pdf_split(source, split_mode.value, split_range.value or "", out_dir, cancel_event)
            log("--- worker: finished split_pdf / split_by_range ---")
            log(f"✓ 完了: {len(files)} ファイルに分割 → {out_dir}")
        except InterruptedError:
            log("Cancelled.")
        except ValueError as ve:
            log(f"⚠ {ve}")
        except Exception as exc:
            log(f"✗ エラー: {exc}")
        finally:
            try:
                hide_busy()
            except Exception as e:
                log(f"⚠ hide_busy failed: {e}")
            split_run_btn.disabled = False
            split_pick_btn.disabled = False
            split_run_btn.update()
            split_pick_btn.update()

    split_pick_btn.on_click = pick_split_source
    split_run_btn.on_click = do_split

    tab_split = ft.Container(
        padding=ft.Padding.all(16),
        content=ft.ListView(
            expand=True,
            spacing=16,
            controls=[
                ft.Text("PDF を分割", size=18, weight=ft.FontWeight.BOLD),
                ft.Row([split_input, split_pick_btn], spacing=8),
                ft.Row([ft.Text("分割モード:", width=90), split_mode]),
                split_range,
                split_output,
                split_run_btn,
            ],
        ),
    )

    return tab_split


async def build_merge_tab(
    *,
    pref_get: Callable[[str, Any], Awaitable[Any]],
    pref_set: Callable[[str, Any], Awaitable[None]],
    choose_file_async: Callable[..., Awaitable[Optional[str]]],
    choose_dir_async: Callable[[], Awaitable[Optional[str]]],
    run_in_thread: Callable[..., Awaitable[Any]],
    log: Callable[[str], None],
    show_busy: Callable[..., Awaitable[None]],
    hide_busy: Callable[[], None],
    default_output_dir: str,
):
    """結合タブを構築して `ft.Container` を返す。"""
    merge_output = OutputDirPicker(
        label="出力先フォルダ（結合）",
        default_dir=str(default_output_dir),
        pref_key="merge.output_dir",
        pref_get=pref_get,
        pref_set=pref_set,
        choose_dir_async=choose_dir_async,
        log=log,
    )
    await merge_output.load()

    merge_mode = ft.RadioGroup(
        value=cast(str, await pref_get("merge.mode", "files")),
        content=ft.Row(
            wrap=True,
            spacing=14,
            run_spacing=6,
            controls=[
                ft.Radio(value="files", label="ファイル選択"),
                ft.Radio(value="folder", label="フォルダ内すべて"),
            ],
        ),
    )

    merge_folder = ft.TextField(label="入力フォルダ（フォルダ結合用）", hint_text="フォルダを選択してください", expand=True)
    merge_folder.value = cast(str, await pref_get("merge.last_folder", ""))

    merge_out_name = ft.TextField(
        label="出力ファイル名（.pdf）",
        value=cast(str, await pref_get("merge.output_name", "merged.pdf")),
        width=320,
    )

    merge_list = ft.ListView(expand=True, height=160, spacing=6)
    merge_paths: list[str] = []

    btn_pick_folder = ft.Button(content="フォルダ選択", width=110)
    btn_add_files = ft.Button(content="PDFを追加", icon=ft.Icons.ADD)
    btn_clear_files = ft.Button(content="リストをクリア", icon=ft.Icons.CLEAR_ALL)

    merge_run_btn = ft.Button(
        content="結合実行",
        icon=ft.Icons.PLAY_ARROW,
        bgcolor=ft.Colors.ORANGE_600,
        color=ft.Colors.WHITE,
        width=200,
    )

    async def merge_mode_changed(e: ft.Event) -> None:
        await pref_set("merge.mode", merge_mode.value)

    async def merge_out_name_changed(e: ft.Event) -> None:
        await pref_set("merge.output_name", merge_out_name.value or "merged.pdf")

    merge_mode.on_change = merge_mode_changed
    merge_out_name.on_change = merge_out_name_changed

    def refresh_merge_list() -> None:
        merge_list.controls.clear()
        for idx, path in enumerate(list(merge_paths)):

            def make_remove(i: int):
                def _remove(e: ft.Event) -> None:
                    if 0 <= i < len(merge_paths):
                        merge_paths.pop(i)
                        refresh_merge_list()
                return _remove

            merge_list.controls.append(
                ft.Row(
                    [
                        ft.Icon(ft.Icons.PICTURE_AS_PDF, color=ft.Colors.RED_400),
                        ft.Text(Path(path).name, expand=True, size=12),
                        ft.IconButton(icon=ft.Icons.REMOVE_CIRCLE_OUTLINE, tooltip="削除", on_click=make_remove(idx)),
                    ]
                )
            )

    async def pick_merge_folder(e: ft.Event) -> None:
        res = await choose_dir_async()
        if isinstance(res, str) and res:
            merge_folder.value = res
            await pref_set("merge.last_folder", res)

    async def add_merge_files(e: ft.Event) -> None:
        res = await choose_file_async(multiple=True)
        if isinstance(res, list):
            for f in res:
                if f and f.lower().endswith(".pdf") and f not in merge_paths:
                    merge_paths.append(f)
        elif isinstance(res, str):
            if res.lower().endswith(".pdf") and res not in merge_paths:
                merge_paths.append(res)
        refresh_merge_list()

    def clear_merge_files(e: ft.Event) -> None:
        merge_paths.clear()
        refresh_merge_list()

    btn_pick_folder.on_click = pick_merge_folder
    btn_add_files.on_click = add_merge_files
    btn_clear_files.on_click = clear_merge_files

    async def do_merge(e: ft.Event) -> None:
        out_dir = merge_output.value
        if not out_dir:
            log("⚠ 出力先フォルダ（結合）を設定してください")
            return
        _ensure_dir(out_dir)

        out_name = (merge_out_name.value or "merged.pdf").strip()
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"
        out_path = str(Path(out_dir) / out_name)

        merge_run_btn.disabled = True
        btn_pick_folder.disabled = True
        btn_add_files.disabled = True
        btn_clear_files.disabled = True
        cancel_event = Event()
        try:
            await show_busy("PDF 結合中...", cancel_event)
        except Exception as e:
            log(f"⚠ show_busy failed: {e}")

        try:
            log(f"▶ 結合開始")
            log("--- worker: start merge_pdfs / merge_folder ---")
            result = await pdf_marge(merge_mode.value, merge_paths, merge_folder.value if merge_folder else "", out_path, cancel_event)
            log("--- worker: finished merge_pdfs / merge_folder ---")
            log(f"✓ 完了: {result}")
        except InterruptedError:
            log("Cancelled.")
        except ValueError as ve:
            log(f"⚠ {ve}")
        except Exception as exc:
            log(f"✗ エラー: {exc}")
        finally:
            try:
                hide_busy()
            except Exception as e:
                log(f"⚠ hide_busy failed: {e}")
            merge_run_btn.disabled = False
            btn_pick_folder.disabled = False
            btn_add_files.disabled = False
            btn_clear_files.disabled = False
            merge_run_btn.update()
            btn_pick_folder.update()
            btn_add_files.update()
            btn_clear_files.update()

    merge_run_btn.on_click = do_merge

    tab_merge = ft.Container(
        padding=ft.Padding.all(16),
        content=ft.ListView(
            expand=True,
            spacing=16,
            controls=[
                ft.Text("PDF を結合", size=18, weight=ft.FontWeight.BOLD),
                ft.Row([ft.Text("結合モード:", width=90), merge_mode]),
                ft.Row([merge_folder, btn_pick_folder], spacing=8),
                ft.Row([btn_add_files, btn_clear_files], spacing=8),
                merge_list,
                merge_out_name,
                merge_output,
                merge_run_btn,
            ],
        ),
    )

    return tab_merge


# ── 出力先の入力フォームを定義 (per tab) ──────────────────────────────────────────
class OutputDirPicker(ft.Row):
    """SharedPreferences にタブごとの出力フォルダを保存するためのピッカー"""

    def __init__(
        self,
        *,
        label: str,
        default_dir: str,
        pref_key: str,
        pref_get: Callable[[str, object], Awaitable[object]],
        pref_set: Callable[[str, object], Awaitable[None]],
        choose_dir_async: Callable[[], Awaitable[Optional[str]]],
        log: Callable[[str], None],
        open_folder: Callable[[str], None] = _open_folder_windows,
    ):
        # クラス初期化 — OutputDirPicker インスタンスを構築しイベントを紐付ける
        super().__init__()
        self._label = label
        self._default_dir = default_dir
        self._pref_key = pref_key
        self._pref_get = pref_get
        self._pref_set = pref_set
        self._choose_dir_async = choose_dir_async
        self._log = log
        self._open_folder = open_folder

        self.field = ft.TextField(label=self._label, read_only=True, expand=True)
        self.btn_pick = ft.Button(content="選択", width=90)
        self.btn_open = ft.Button(content="開く", icon=ft.Icons.FOLDER_OPEN, width=90)

        self.btn_pick.on_click = self._pick
        self.btn_open.on_click = self._open

        self.controls = [self.field, self.btn_pick, self.btn_open]
        self.spacing = 8
        self.vertical_alignment = ft.CrossAxisAlignment.CENTER

    @property
    def value(self) -> str:
        # インスタンスプロパティ — 現在の入力値（フィールドの文字列）を取得する
        return (self.field.value or "").strip()

    async def load(self) -> None:
        # インスタンスメソッド（非同期） — SharedPreferences から出力先を読み込む
        v = await self._pref_get(self._pref_key, self._default_dir)
        self.field.value = str(v) if v else self._default_dir
        _ensure_dir(self.field.value)

    async def _pick(self, e: ft.Event) -> None:
        # イベントハンドラ（非公開） — ユーザーが出力フォルダを選択したときに動作する
        res = await self._choose_dir_async()
        if res and str(res).strip():
            folder = str(res).strip()
            self.field.value = folder
            _ensure_dir(folder)
            await self._pref_set(self._pref_key, folder)
            self.update()

    def _open(self, e: ft.Event) -> None:
        # イベントハンドラ（非公開） — 選択したフォルダをエクスプローラで開く
        if not self.value:
            return
        try:
            self._open_folder(self.value)
        except Exception:
            self._log("⚠ フォルダを開けませんでした（権限/パスを確認してください）")


async def main(page: ft.Page) -> None:
    # ── ページ設定 ─────────────────────────────────────────────────────
    page.title = APP_NAME
    adhust_sindow_size(page)
    page.padding = 20
    page.theme_mode = ft.ThemeMode.LIGHT

    DEFAULT_OUTPUT_DIR.mkdir(exist_ok=True)
    INPUT_DIR.mkdir(exist_ok=True)

    # ── SharedPreferences（設定保存） ──────────────────────────────────────────────
    prefs = ft.SharedPreferences()

    def _k(key: str) -> str:
        # main 内ヘルパー（ローカル） — SharedPreferences 用のキーにプレフィックスを付与する純粋関数
        return f"{PREF_PREFIX}{key}"

    async def pref_get(key: str, default: Any) -> Any:
        # main 内非同期ユーティリティ — SharedPreferences から値を取得するラッパー
        try:
            v = await prefs.get(_k(key))
            return default if v is None else v
        except Exception:
            return default

    async def pref_set(key: str, value: Any) -> None:
        # main 内非同期ユーティリティ — SharedPreferences に値を保存するラッパー
        try:
            await prefs.set(_k(key), value)
        except Exception as exc:
            log(f"Preference save failed: {key}: {exc}")

    # ── ログ表示 ────────────────────────────────────────────────────────────
    log_field = ft.TextField(
        multiline=True,
        read_only=True,
        min_lines=6,
        max_lines=10,
        expand=True,
        text_size=12,
        border_color=ft.Colors.BLUE_GREY_200,
    )

    def log(msg: str) -> None:
        # main 内ロガー — UI のログ表示フィールドにメッセージを追記する
        log_field.value = (log_field.value or "") + msg + "\n"
        page.update()

    def clear_log(e: ft.Event) -> None:
        # main 内イベントハンドラ — ログ表示をクリアするボタンの処理
        log_field.value = ""
        page.update()

    # ── 非同期ユーティリティ ───────────────────────────────────────────────────
    async def run_in_thread(func, *args, **kwargs):
        # main 内ユーティリティ（非同期） — ブロッキング関数をスレッドで実行する
        return await asyncio.to_thread(func, *args, **kwargs)

    async def choose_file_async(multiple: bool = False):
        # main 内ユーティリティ（非同期） — tkinter のファイル選択を非同期でラップ
        return await asyncio.to_thread(_tk_choose_file, multiple)

    async def choose_dir_async():
        # main 内ユーティリティ（非同期） — tkinter のディレクトリ選択を非同期でラップ
        return await asyncio.to_thread(_tk_choose_dir)

    # ── 処理中ダイアログ（page.open/page.close） ──────────────────────────────
    busy_text = ft.Text("処理中...", size=14)
    current_cancel_event: Event | None = None

    def request_cancel(e: ft.Event) -> None:
        nonlocal current_cancel_event
        if current_cancel_event is None:
            return
        current_cancel_event.set()
        cancel_button.disabled = True
        log("Cancel requested.")

    cancel_button = ft.Button(content="Cancel", icon=ft.Icons.CANCEL, on_click=request_cancel)
    busy_dialog = ft.AlertDialog(
        modal=True,
        content=ft.Container(
            padding=ft.Padding.all(20),
            content=ft.Column(
                [
                    ft.Row(
                        [ft.ProgressRing(), busy_text],
                        spacing=16,
                        alignment=ft.MainAxisAlignment.CENTER,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row([cancel_button], alignment=ft.MainAxisAlignment.END),
                ],
                tight=True,
                spacing=16,
            ),
        ),
    )

    async def show_busy(message: str, cancel_event: Event | None = None) -> None:
        # main 内 UI ヘルパー（非同期） — モーダルの「処理中」ダイアログを表示する
        nonlocal current_cancel_event
        current_cancel_event = cancel_event
        busy_text.value = message
        cancel_button.visible = cancel_event is not None
        cancel_button.disabled = False
        if busy_dialog not in page.overlay:
            page.overlay.append(busy_dialog)
        busy_dialog.open = True
        page.update()
        await asyncio.sleep(0)

    def hide_busy() -> None:
        # main 内 UI ヘルパー — モーダルの「処理中」ダイアログを閉じる
        nonlocal current_cancel_event
        busy_dialog.open = False
        current_cancel_event = None
        cancel_button.disable = True

        page.update()
        
        asyncio.sleep(0)

    # ════════════════════════════════════════════════════════════════════
    # TAB 1: PDF → 画像
    # Order: mode → input → options → output → run
    # ════════════════════════════════════════════════════════════════════
    tab_convert = await build_convert_tab(
        pref_get=pref_get,
        pref_set=pref_set,
        choose_file_async=choose_file_async,
        choose_dir_async=choose_dir_async,
        run_in_thread=run_in_thread,
        log=log,
        show_busy=show_busy,
        hide_busy=hide_busy,
        default_output_dir=str(DEFAULT_OUTPUT_DIR),
    )

    # ════════════════════════════════════════════════════════════════════
    # TAB 2: PDF 分割
    # Order: input → mode → output → run
    # ════════════════════════════════════════════════════════════════════
    tab_split = await build_split_tab(
        pref_get=pref_get,
        pref_set=pref_set,
        choose_file_async=choose_file_async,
        choose_dir_async=choose_dir_async,
        run_in_thread=run_in_thread,
        log=log,
        show_busy=show_busy,
        hide_busy=hide_busy,
        default_output_dir=str(DEFAULT_OUTPUT_DIR),
    )

    # ════════════════════════════════════════════════════════════════════
    # TAB 3: PDF 結合
    # Order: input → options → output → run
    # ════════════════════════════════════════════════════════════════════
    tab_merge = await build_merge_tab(
        pref_get=pref_get,
        pref_set=pref_set,
        choose_file_async=choose_file_async,
        choose_dir_async=choose_dir_async,
        run_in_thread=run_in_thread,
        log=log,
        show_busy=show_busy,
        hide_busy=hide_busy,
        default_output_dir=str(DEFAULT_OUTPUT_DIR),
    )

    # ── タブ（TabBar + TabBarView） ──────────────────────────────────────
    tab_bar = ft.TabBar(
        tabs=[
            ft.Tab(label="PDF → 画像"),
            ft.Tab(label="PDF 分割"),
            ft.Tab(label="PDF 結合"),
        ]
    )
    tab_view = ft.TabBarView(expand=True, controls=[tab_convert, tab_split, tab_merge])
    tabs = ft.Tabs(expand=True, length=3, content=ft.Column([tab_bar, tab_view], expand=True))

    # ── ログ（デフォルトで折りたたみ） ──────────────────────────────────────
    # ExpansionTile は開閉状態を "expanded" で制御します。[1](https://flet.dev/docs/controls/expansiontile/)
    log_tile = ft.ExpansionTile(
        title=ft.Row(
            [
                ft.Text("ログ", weight=ft.FontWeight.BOLD),
                ft.TextButton("クリア", on_click=clear_log),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        expanded=False,  # default hidden
        controls=[log_field],
        controls_padding=ft.Padding.only(top=8, left=4, right=4, bottom=4),
    )

    # ── Layout ─────────────────────────────────────────────────────────
    page.add(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.PICTURE_AS_PDF, size=30, color=ft.Colors.RED_500),
                        ft.Text("PDF Editor", size=26, weight=ft.FontWeight.BOLD),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Divider(),
                tabs,
                ft.Divider(),
                log_tile,
            ],
            expand=True,
        )
    )
