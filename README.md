# pdf-editor

PDF を JPEG / PNG 画像へ変換し、PDF の分割・結合も行える Flet 製 GUI
アプリケーションです。

## 必要環境

- Python 3.12
- [uv](https://docs.astral.sh/uv/)

依存関係の正本は `pyproject.toml`、再現可能な解決結果は `uv.lock` です。
重複管理を避けるため、旧 `requirements.txt` は削除しました。

## セットアップ

リポジトリのルートで次を実行します。

```powershell
uv sync
```

## 起動

正式な開発時の起動コマンドは次のとおりです。

```powershell
uv run python main.py
```

ルートの `main.py` は Flet を起動し、`src.gui.app` の GUI
エントリーポイントを呼び出すだけの薄い起動ファイルです。

Flet CLI のリロード機能を使う場合は、次のコマンドでも起動できます。

```powershell
uv run flet run main.py
```

## Windows ビルド

```powershell
uv run flet build windows
```

生成物は `build/windows/` に出力されます。Flet 0.85.1 は
`assets/icon.png` をビルド用アイコンとして自動検出します。
`assets/app.ico` は既存の Windows 用 ICO 素材です。

## プロジェクト構成

```text
pdf-editor/
├── main.py                  # 正式な起動ファイル
├── pyproject.toml           # プロジェクト設定・依存関係の正本
├── uv.lock                  # 固定済み依存関係
├── README.md
├── assets/
│   ├── app.ico              # Windows 用 ICO 素材
│   └── icon.png             # Flet ビルド用アプリアイコン
├── input/                   # 既定の入力場所
├── output/                  # 既定の出力場所
├── src/
│   ├── __init__.py
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── app.py           # 現在の Flet GUI 実装
│   │   ├── pdf_drop_field.py # 共通 PDF 入力コンポーネント
│   │   └── assets/          # GUI 内部専用素材（現在は空）
│   ├── pdf_input.py          # PDF 入力パスの検証
│   ├── output_paths.py
│   ├── pdf_merge.py
│   ├── pdf_split.py
│   ├── pdf_to_img.py
│   └── platform_utils.py
└── tests/
```

既定の `input/` と `output/` は、カレントディレクトリではなくソースの
配置場所を基準に解決されます。そのため、別のディレクトリから
`main.py` を指定して起動しても同じ場所を参照します。ユーザーが GUI
で選んだ出力先と既存の SharedPreferences キーは変更していません。

## PDF ファイル入力

各タブのPDF入力領域は、クリックまたは既存の選択ボタンから同じ
ファイル選択ダイアログを開きます。拡張子、存在、読み取り可否、重複を
検証し、受け付けたファイルはパスとサイズを含む一覧に表示します。

Flet 0.85.1 の `DragTarget` はFlet画面内の `Draggable` 専用で、OSの
エクスプローラーからファイルパスを受け取る正式APIはありません。
そのため、このバージョンではネイティブなファイルドロップは利用できず、
クリックによる `FilePicker` をフォールバックとして使用します。

## 機能

### PDF → 画像

- 単一 PDF または指定フォルダ内の PDF を JPEG / PNG に変換
- 解像度を選択可能

### PDF 分割

- 全ページを 1 ページずつ分割
- `1-3, 5, 7-9` 形式でページ範囲を指定して分割

### PDF 結合

- 選択した複数 PDF を指定順に結合
- 指定フォルダ内の PDF をファイル名順に結合

## assets の用途

- ルート `assets/`: アプリ全体および Flet / Windows ビルドで使う素材
- `src/gui/assets/`: GUI 画面内部だけで使う静的素材の配置先

パスは `pathlib.Path` とモジュールの配置場所を基準に解決し、
`Path.cwd()` には依存しません。

## 既知の制約

- GUI のクラス化は未実装です。
- ドラッグ＆ドロップは未実装です。
- レスポンシブなドロップ領域は未実装です。

これらは次回以降の変更対象です。今回の構成整理では、既存 UI、イベント処理、
SharedPreferences キー、PDF 処理関数の引数と戻り値を変更していません。

## ライセンス

[LICENSE](LICENSE) を参照してください。
