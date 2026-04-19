from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

JST = timezone(timedelta(hours=9))


@dataclass
class PostData:
    row_index: int
    scheduled_at: datetime
    text: str
    image_urls: list[str]
    status: str


class SpreadsheetClient:
    def __init__(self, credentials_path: str) -> None:
        creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
        self._client = gspread.authorize(creds)

    def get_pending_posts(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        time_window_minutes: int,
    ) -> list[PostData]:
        sheet = self._client.open_by_key(spreadsheet_id).worksheet(sheet_name)
        rows = sheet.get_all_values()

        now = datetime.now(JST)
        window_start = now - timedelta(minutes=time_window_minutes)

        results: list[PostData] = []
        for i, row in enumerate(rows[1:], start=2):  # skip header, row_index is 1-based
            if len(row) < 7:
                row = row + [""] * (7 - len(row))

            status = row[6].strip()
            if status != "未投稿":
                continue

            try:
                scheduled_at = datetime.strptime(row[0].strip(), "%Y/%m/%d %H:%M").replace(tzinfo=JST)
            except ValueError:
                continue

            if not (window_start <= scheduled_at <= now):
                continue

            image_urls = [url.strip() for url in row[2:6] if url.strip()]

            results.append(PostData(
                row_index=i,
                scheduled_at=scheduled_at,
                text=row[1],
                image_urls=image_urls,
                status=status,
            ))

        results.sort(key=lambda p: p.scheduled_at)
        return results

    def update_status(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        row_index: int,
        status: str,
    ) -> None:
        sheet = self._client.open_by_key(spreadsheet_id).worksheet(sheet_name)
        # Column G is index 7
        sheet.update_cell(row_index, 7, status)

    def write_log(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        level: str,
        message: str,
        detail: str = "",
    ) -> None:
        sheet = self._client.open_by_key(spreadsheet_id).worksheet(sheet_name)
        timestamp = datetime.now(JST).strftime("%Y/%m/%d %H:%M:%S")
        sheet.append_row([timestamp, level, message, detail])
