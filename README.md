# tojibot

Google Spreadsheetに登録された投稿予定データに基づき、Playwright + ヘッドレスChromeを使用してX（旧Twitter）へ自動投稿するPythonアプリケーション。

## 必要環境

- Ubuntu
- Python 3.11以上
- [uv](https://docs.astral.sh/uv/)

## セットアップ手順

### 1. リポジトリのクローン

```bash
git clone https://github.com/eidas/tojibot.git
cd tojibot
```

### 2. 依存パッケージのインストール

```bash
uv sync
```

### 3. Playwright用Chromiumのインストール

```bash
uv run playwright install chromium
uv run playwright install-deps
```

### 4. GCPサービスアカウントの設定

1. [Google Cloud Console](https://console.cloud.google.com/) でサービスアカウントを作成
2. 以下のAPIを有効化:
   - Google Sheets API
   - Google Drive API
3. サービスアカウントのJSONキーをダウンロードし、`credentials/service_account.json` に配置
4. パーミッションを制限:
   ```bash
   chmod 600 credentials/service_account.json
   ```
5. 対象スプレッドシートの編集権限をサービスアカウントのメールアドレスに共有

### 5. スプレッドシートの準備

**投稿予定シート**（列構成）:

| 列 | カラム名 | 形式・備考 |
|----|---------|-----------|
| A | 投稿日時 | `YYYY/MM/DD HH:MM` |
| B | テキスト | 投稿本文 |
| C | 画像1 | Google Drive共有URL（空欄可） |
| D | 画像2 | Google Drive共有URL（空欄可） |
| E | 画像3 | Google Drive共有URL（空欄可） |
| F | 画像4 | Google Drive共有URL（空欄可） |
| G | ステータス | `未投稿` / `投稿済み` / `失敗` |

**ログシート**（別スプレッドシートでも可）:

| 列 | カラム名 |
|----|---------|
| A | タイムスタンプ |
| B | レベル |
| C | メッセージ |
| D | 詳細 |

### 6. 環境変数の設定

```bash
cp .env.example .env
chmod 600 .env
```

`.env` を編集して各値を設定:

```env
# Google
GCP_SERVICE_ACCOUNT_JSON=credentials/service_account.json
SPREADSHEET_ID_POSTS=<投稿予定スプレッドシートのID>
SPREADSHEET_ID_LOGS=<ログスプレッドシートのID>
SHEET_NAME_POSTS=投稿予定
SHEET_NAME_LOGS=ログ

# X (Twitter)
X_USERNAME=<XのユーザーID>
X_PASSWORD=<Xのパスワード>

# Gmail SMTP
GMAIL_ADDRESS=<Gmailアドレス>
GMAIL_APP_PASSWORD=<Googleアプリパスワード>
NOTIFY_TO=<通知先メールアドレス>
```

> **Gmail アプリパスワードの取得方法:** Googleアカウントの2段階認証を有効にし、「セキュリティ」→「アプリパスワード」から発行する。

### 7. 動作確認

```bash
uv run python -m tojibot.main
```

## cron設定

15分ごとに実行し、多重起動を防止する設定例:

```bash
# crontab -e
*/15 * * * * /usr/bin/flock -n /tmp/tojibot.lock /path/to/tojibot/scripts/run.sh >> /var/log/tojibot/cron.log 2>&1
```

ログディレクトリの作成:

```bash
sudo mkdir -p /var/log/tojibot
sudo chown $USER /var/log/tojibot
```

`scripts/run.sh` 内の `uv` パスを環境に合わせて修正:

```bash
which uv  # パスを確認
```

## エラー時の対応

- 投稿に失敗した場合、ステータスが `失敗` に更新され、`NOTIFY_TO` 宛にメール通知が送信される。
- 手動で再実行するには、スプレッドシートのステータスを `未投稿` に戻す。
- エラー発生時のスクリーンショットは `/tmp/tojibot/screenshots/` に保存される。
