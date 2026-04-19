from __future__ import annotations

import traceback
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tojibot.spreadsheet import SpreadsheetClient

JST = timezone(timedelta(hours=9))


class SheetLogger:
    def __init__(
        self,
        spreadsheet_client: SpreadsheetClient,
        spreadsheet_id: str,
        sheet_name: str,
    ) -> None:
        self._client = spreadsheet_client
        self._spreadsheet_id = spreadsheet_id
        self._sheet_name = sheet_name

    def info(self, message: str, detail: str = "") -> None:
        self._log("INFO", message, detail)

    def warning(self, message: str, detail: str = "") -> None:
        self._log("WARNING", message, detail)

    def error(self, message: str, detail: str = "") -> None:
        self._log("ERROR", message, detail)

    def _log(self, level: str, message: str, detail: str) -> None:
        ts = datetime.now(JST).strftime("%Y/%m/%d %H:%M:%S")
        print(f"[{ts}] [{level}] {message}" + (f"\n{detail}" if detail else ""))
        try:
            self._client.write_log(
                self._spreadsheet_id,
                self._sheet_name,
                level,
                message,
                detail,
            )
        except Exception as e:
            print(f"[{ts}] [WARNING] ログシートへの書き込みに失敗しました: {e}")
