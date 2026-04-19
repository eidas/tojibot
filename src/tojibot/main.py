import asyncio
import traceback
import time

from tojibot.config import config
from tojibot.spreadsheet import SpreadsheetClient
from tojibot.drive import DriveDownloader
from tojibot.poster import XPoster
from tojibot.notifier import EmailNotifier
from tojibot.logger import SheetLogger


def main() -> None:
    sheet_client = SpreadsheetClient(config.GCP_SERVICE_ACCOUNT_JSON)
    logger = SheetLogger(sheet_client, config.SPREADSHEET_ID_LOGS, config.SHEET_NAME_LOGS)
    notifier = EmailNotifier(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD, config.NOTIFY_TO)

    logger.info("tojibot 起動")

    try:
        posts = sheet_client.get_pending_posts(
            config.SPREADSHEET_ID_POSTS,
            config.SHEET_NAME_POSTS,
            config.POST_TIME_WINDOW_MINUTES,
        )
    except Exception as e:
        detail = traceback.format_exc()
        logger.error("スプレッドシートの読み取りに失敗しました", detail)
        _try_notify(notifier, "tojibot: スプレッドシート読み取り失敗", f"{e}\n\n{detail}")
        return

    if not posts:
        logger.info("投稿対象なし。終了します。")
        return

    logger.info(f"{len(posts)} 件の投稿対象を検出しました")

    drive = DriveDownloader(config.GCP_SERVICE_ACCOUNT_JSON)
    poster = XPoster(config.X_USERNAME, config.X_PASSWORD)

    for i, post in enumerate(posts):
        logger.info(f"投稿開始: row={post.row_index} scheduled_at={post.scheduled_at}")

        image_paths = []
        try:
            if post.image_urls:
                image_paths = drive.download_images(post.image_urls)
        except Exception as e:
            detail = traceback.format_exc()
            logger.error(f"画像ダウンロード失敗: row={post.row_index}", detail)
            sheet_client.update_status(
                config.SPREADSHEET_ID_POSTS, config.SHEET_NAME_POSTS, post.row_index, "失敗"
            )
            _try_notify(notifier, "tojibot: 画像ダウンロード失敗", f"row={post.row_index}\n{e}\n\n{detail}")
            continue

        try:
            asyncio.run(poster.post(post.text, image_paths))
            sheet_client.update_status(
                config.SPREADSHEET_ID_POSTS, config.SHEET_NAME_POSTS, post.row_index, "投稿済み"
            )
            logger.info(f"投稿完了: row={post.row_index}")
        except Exception as e:
            detail = traceback.format_exc()
            logger.error(f"X投稿失敗: row={post.row_index}", detail)
            sheet_client.update_status(
                config.SPREADSHEET_ID_POSTS, config.SHEET_NAME_POSTS, post.row_index, "失敗"
            )
            _try_notify(notifier, "tojibot: X投稿失敗", f"row={post.row_index}\n{e}\n\n{detail}")
        finally:
            drive.cleanup(image_paths)

        if i < len(posts) - 1:
            time.sleep(config.POST_INTERVAL_SECONDS)

    logger.info("tojibot 終了")


def _try_notify(notifier: EmailNotifier, subject: str, body: str) -> None:
    try:
        notifier.send_error(subject, body)
    except Exception as e:
        print(f"メール通知の送信に失敗しました: {e}")


if __name__ == "__main__":
    main()
