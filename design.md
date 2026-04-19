# tojibot 設計書

## 1. システム概要

tojibotは、Google Spreadsheetに登録された投稿予定データに基づき、Playwright＋ヘッドレスChromeを使用してX（旧Twitter）への自動投稿を行うPythonアプリケーションである。

### 1.1 システム構成図

```
┌─────────┐    cron (15分毎)     ┌───────────┐
│  Ubuntu  │ ──────────────────► │  tojibot  │
│  Server  │                     │ (Python)  │
└─────────┘                     └─────┬─────┘
                                      │
                 ┌────────────────────┼────────────────────┐
                 │                    │                    │
                 ▼                    ▼                    ▼
        ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
        │    Google       │  │   Google       │  │       X        │
        │  Spreadsheet   │  │    Drive       │  │  (via Chrome)  │
        │  (投稿予定/ログ) │  │  (画像取得)    │  │  (Playwright)  │
        └────────────────┘  └────────────────┘  └────────────────┘
                                                        │
                                                失敗時  ▼
                                                ┌────────────────┐
                                                │  Gmail SMTP    │
                                                │  (メール通知)   │
                                                └────────────────┘
```

### 1.2 技術スタック

| 項目 | 技術 |
|------|------|
| OS | Ubuntu |
| 言語 | Python 3 |
| パッケージ管理 | uv |
| ブラウザ自動操作 | Playwright (Chromium, ヘッドレス) |
| スプレッドシート操作 | gspread + google-auth |
| 画像取得 | Google Drive URL経由 (requests) |
| メール通知 | smtplib (Gmail SMTP) |
| 定期実行 | cron |

---

## 2. ディレクトリ構成

```
tojibot/
├── .env                     # 環境変数（秘匿情報）
├── .env.example             # .envのテンプレート
├── pyproject.toml           # uv / プロジェクト設定
├── uv.lock                  # 依存関係ロック
├── credentials/
│   └── service_account.json # GCPサービスアカウント鍵
├── src/
│   └── tojibot/
│       ├── __init__.py
│       ├── main.py          # エントリポイント
│       ├── config.py        # 設定読み込み (.env)
│       ├── spreadsheet.py   # Google Spreadsheet操作
│       ├── drive.py         # Google Drive画像取得
│       ├── poster.py        # X投稿処理 (Playwright)
│       ├── notifier.py      # メール通知
│       └── logger.py        # ログ出力 (Spreadsheet)
├── scripts/
│   └── run.sh               # cron用起動スクリプト
└── README.md
```

---

## 3. 設定管理

### 3.1 .env ファイル

```env
# Google
GCP_SERVICE_ACCOUNT_JSON=credentials/service_account.json
SPREADSHEET_ID_POSTS=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SPREADSHEET_ID_LOGS=yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
SHEET_NAME_POSTS=投稿予定
SHEET_NAME_LOGS=ログ

# X (Twitter)
X_USERNAME=your_username
X_PASSWORD=your_password

# Gmail SMTP
GMAIL_ADDRESS=your_email@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
NOTIFY_TO=recipient@example.com

# アプリ設定
POST_INTERVAL_SECONDS=60
IMAGE_ATTACH_INTERVAL_SECONDS=5
POST_TIME_WINDOW_MINUTES=15
```

### 3.2 config.py

`.env`を読み込み、各モジュールが参照する設定オブジェクトを提供する。`pydantic-settings`または`python-dotenv`で実装する。

---

## 4. Google Spreadsheet 仕様

### 4.1 投稿予定シート

GCPサービスアカウント（JSON鍵）で認証し、`gspread`ライブラリで操作する。

| 列 | カラム名 | 型 | 説明 |
|----|---------|-----|------|
| A | 投稿日時 | datetime | `YYYY/MM/DD HH:MM` 形式 |
| B | テキスト | string | 投稿本文 |
| C | 画像1 | string | Google Drive共有URL（空欄可） |
| D | 画像2 | string | Google Drive共有URL（空欄可） |
| E | 画像3 | string | Google Drive共有URL（空欄可） |
| F | 画像4 | string | Google Drive共有URL（空欄可） |
| G | ステータス | string | `未投稿` / `投稿済み` / `失敗` |

**補足:**

- サービスアカウントにスプレッドシートの編集権限を共有しておくこと。
- 画像URLはGoogle Driveの共有リンク形式（`https://drive.google.com/file/d/FILE_ID/...`）を想定。

### 4.2 ログシート

投稿予定シートとは別のスプレッドシートにログを出力する。

| 列 | カラム名 | 型 | 説明 |
|----|---------|-----|------|
| A | タイムスタンプ | datetime | ログ出力日時 |
| B | レベル | string | `INFO` / `WARNING` / `ERROR` |
| C | メッセージ | string | ログメッセージ |
| D | 詳細 | string | エラートレースバック等（任意） |

---

## 5. モジュール設計

### 5.1 main.py（エントリポイント）

メイン処理フローを制御する。

```
処理フロー:
1. 設定読み込み (config)
2. ログ初期化 (logger)
3. 投稿予定データ取得 (spreadsheet)
4. 投稿対象のフィルタリング（時間窓判定）
5. 対象なし → 正常終了
6. 対象あり → 1件ずつ以下を実行:
   a. 画像ダウンロード (drive)
   b. X投稿実行 (poster)
   c. ステータス更新 (spreadsheet)
   d. ログ記録 (logger)
   e. 次の投稿まで待機（POST_INTERVAL_SECONDS）
7. 失敗時 → メール通知 (notifier) + ログ記録
8. 終了
```

### 5.2 spreadsheet.py（Google Spreadsheet操作）

**責務:** 投稿予定データの読み出し、ステータス更新、ログ書き込み。

```python
class SpreadsheetClient:
    def __init__(self, credentials_path: str)
    def get_pending_posts(self, spreadsheet_id, sheet_name, time_window_minutes) -> list[PostData]
    def update_status(self, spreadsheet_id, sheet_name, row_index, status: str) -> None
    def write_log(self, spreadsheet_id, sheet_name, level, message, detail="") -> None
```

**PostDataモデル:**

```python
@dataclass
class PostData:
    row_index: int          # シート上の行番号（ステータス更新用）
    scheduled_at: datetime  # 投稿予定日時
    text: str               # 投稿テキスト
    image_urls: list[str]   # 画像URL（0〜4件）
    status: str             # 現在のステータス
```

**投稿対象の判定ロジック:**

```
対象条件:
  ステータス == "未投稿"
  AND 現在時刻 - 投稿日時 >= 0（予定時刻を過ぎている）
  AND 現在時刻 - 投稿日時 <= POST_TIME_WINDOW_MINUTES（15分以内）

結果は投稿日時の昇順にソートして返す。
```

### 5.3 drive.py（Google Drive画像取得）

**責務:** Google DriveのURLから画像ファイルをダウンロードし、一時ファイルとして保存する。

```python
class DriveDownloader:
    def __init__(self, credentials_path: str)
    def download_images(self, urls: list[str]) -> list[Path]
    def cleanup(self, paths: list[Path]) -> None
```

**処理詳細:**

- Google Drive共有URLからファイルIDを抽出する。
- Google Drive API（サービスアカウント認証）でファイルをダウンロードする。
- 一時ディレクトリ（`/tmp/tojibot/`）に保存する。
- 投稿完了後に`cleanup`で一時ファイルを削除する。

### 5.4 poster.py（X投稿処理）

**責務:** Playwrightでヘッドレスchromeを操作し、Xにログイン・投稿する。

```python
class XPoster:
    def __init__(self, username: str, password: str)
    async def post(self, text: str, image_paths: list[Path]) -> bool
```

**処理フロー:**

```
1. ブラウザ起動（Chromium, ヘッドレスモード）
2. X（https://x.com）にアクセス
3. ページ状態を判定:
   a. ログイン画面が表示 → ログイン処理を実行
   b. ホーム画面が表示（Cookie自動ログイン） → そのまま続行
   c. その他の画面 → エラーとして処理
4. 投稿画面へ遷移
5. テキスト入力
6. 画像添付（1枚ずつ、5秒間隔）
7. 投稿ボタンクリック
8. 投稿完了の確認（DOM要素の変化を検知）
9. ブラウザ終了
```

**ページ状態判定の詳細:**

```
判定方法: 特定のDOM要素の存在チェック

ログイン画面:
  - ユーザー名入力フィールドの存在
  - "Sign in" / "Log in" テキストの存在

ホーム画面（自動ログイン済み）:
  - 投稿ボタンまたはツイート入力欄の存在
  - ナビゲーションメニューの存在

不明な画面:
  - 上記いずれにも該当しない場合
  - スクリーンショットを保存してエラーログに記録
```

**ログイン処理の詳細:**

```
1. ユーザー名入力フィールドにX_USERNAMEを入力
2. 「次へ」ボタンをクリック
3. パスワード入力フィールドの表示を待機
4. パスワード入力フィールドにX_PASSWORDを入力
5. 「ログイン」ボタンをクリック
6. ホーム画面への遷移を待機（タイムアウト: 30秒）
7. 遷移失敗 → エラー
```

**投稿処理の詳細:**

```
1. 投稿入力欄をクリック（フォーカス）
2. テキストを入力（Playwright の fill または type を使用）
3. 画像がある場合:
   a. 画像添付ボタンの input[type="file"] を取得
   b. 1枚目の画像ファイルパスを set_input_files で設定
   c. アップロード完了を待機（プレビュー表示の検知）
   d. 5秒待機
   e. 2枚目以降も同様に繰り返す
4. 投稿ボタン（"Post" / "ポスト"）をクリック
5. 投稿完了を確認:
   - 投稿入力欄がクリアされたことを検知
   - または成功トーストの表示を検知
6. 確認できない場合 → タイムアウトでエラー
```

**タイムアウト設定:**

| 操作 | タイムアウト |
|------|------------|
| ページ読み込み | 30秒 |
| ログイン完了待機 | 30秒 |
| 画像アップロード待機 | 15秒/枚 |
| 投稿完了待機 | 30秒 |

### 5.5 notifier.py（メール通知）

**責務:** 投稿失敗時にGmail SMTP経由でメール通知を送信する。

```python
class EmailNotifier:
    def __init__(self, gmail_address, app_password, notify_to)
    def send_error(self, subject: str, body: str) -> None
```

**実装方針:**

- `smtplib` + `ssl` を使用。
- GmailのSMTPサーバー（`smtp.gmail.com:587`）にTLS接続。
- Googleアプリパスワードで認証（Gmailの2段階認証を有効にしたうえでアプリパスワードを発行）。

### 5.6 logger.py（ログ出力）

**責務:** ログをGoogle Spreadsheetに書き込む。コンソール（stdout）にも同時出力する。

```python
class SheetLogger:
    def __init__(self, spreadsheet_client: SpreadsheetClient)
    def info(self, message: str, detail: str = "") -> None
    def warning(self, message: str, detail: str = "") -> None
    def error(self, message: str, detail: str = "") -> None
```

**実装方針:**

- 各メソッドは`spreadsheet_client.write_log()`を呼び出してシートに追記する。
- 同時に`print()`でコンソールにも出力する（cronログ用）。
- ログシートへの書き込み自体が失敗した場合は、コンソール出力のみにフォールバックする。

---

## 6. エラー処理方針

### 6.1 エラー分類と対応

| エラー種別 | 対応 | ステータス更新 | メール通知 |
|-----------|------|--------------|-----------|
| スプレッドシート読み取り失敗 | 処理中断、ログ出力 | なし | 送信 |
| 画像ダウンロード失敗 | 当該投稿をスキップ | `失敗` | 送信 |
| Xログイン失敗 | 処理中断 | なし | 送信 |
| X投稿失敗 | 当該投稿をスキップ | `失敗` | 送信 |
| メール送信失敗 | コンソールログのみ | - | - |
| ログシート書き込み失敗 | コンソールログにフォールバック | - | - |

### 6.2 リトライ方針

- 本バージョンでは自動リトライは行わない。
- 失敗した投稿は手動でステータスを「未投稿」に戻して再実行する運用とする。

### 6.3 スクリーンショット

- Playwright操作中にエラーが発生した場合、現在のページのスクリーンショットを保存する。
- 保存先: `/tmp/tojibot/screenshots/`
- ファイル名: `error_YYYYMMDD_HHMMSS.png`

---

## 7. cron設定

### 7.1 起動スクリプト（scripts/run.sh）

```bash
#!/bin/bash
cd /path/to/tojibot
/path/to/.local/bin/uv run python -m tojibot.main
```

### 7.2 crontab

```cron
*/15 * * * * /path/to/tojibot/scripts/run.sh >> /var/log/tojibot/cron.log 2>&1
```

**補足:**

- cronの出力は`/var/log/tojibot/cron.log`にリダイレクトする（ログシート書き込み失敗時のフォールバック用）。
- 多重起動防止は`flock`コマンドで対応する。

```cron
*/15 * * * * /usr/bin/flock -n /tmp/tojibot.lock /path/to/tojibot/scripts/run.sh >> /var/log/tojibot/cron.log 2>&1
```

---

## 8. 依存パッケージ

```toml
[project]
name = "tojibot"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "playwright",
    "gspread",
    "google-auth",
    "google-api-python-client",
    "python-dotenv",
    "requests",
]
```

**セットアップ手順:**

```bash
uv sync
uv run playwright install chromium
uv run playwright install-deps
```

---

## 9. セキュリティ考慮事項

| 項目 | 対応 |
|------|------|
| サービスアカウント鍵 | `.gitignore`に追加、ファイルパーミッション`600` |
| `.env`ファイル | `.gitignore`に追加、ファイルパーミッション`600` |
| Xパスワード | `.env`で管理、ログに出力しない |
| Gmailアプリパスワード | `.env`で管理、ログに出力しない |
| スクリーンショット | 個人情報が含まれる可能性あり、定期的に削除 |
