import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    GCP_SERVICE_ACCOUNT_JSON: str = os.environ["GCP_SERVICE_ACCOUNT_JSON"]
    SPREADSHEET_ID_POSTS: str = os.environ["SPREADSHEET_ID_POSTS"]
    SPREADSHEET_ID_LOGS: str = os.environ["SPREADSHEET_ID_LOGS"]
    SHEET_NAME_POSTS: str = os.getenv("SHEET_NAME_POSTS", "投稿予定")
    SHEET_NAME_LOGS: str = os.getenv("SHEET_NAME_LOGS", "ログ")

    X_USERNAME: str = os.environ["X_USERNAME"]
    X_PASSWORD: str = os.environ["X_PASSWORD"]

    GMAIL_ADDRESS: str = os.environ["GMAIL_ADDRESS"]
    GMAIL_APP_PASSWORD: str = os.environ["GMAIL_APP_PASSWORD"]
    NOTIFY_TO: str = os.environ["NOTIFY_TO"]

    POST_INTERVAL_SECONDS: int = int(os.getenv("POST_INTERVAL_SECONDS", "60"))
    IMAGE_ATTACH_INTERVAL_SECONDS: int = int(os.getenv("IMAGE_ATTACH_INTERVAL_SECONDS", "5"))
    POST_TIME_WINDOW_MINUTES: int = int(os.getenv("POST_TIME_WINDOW_MINUTES", "15"))


config = Config()
