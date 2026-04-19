import re
import tempfile
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
TMP_DIR = Path("/tmp/tojibot")

_FILE_ID_PATTERNS = [
    re.compile(r"/file/d/([a-zA-Z0-9_-]+)"),
    re.compile(r"[?&]id=([a-zA-Z0-9_-]+)"),
]


def _extract_file_id(url: str) -> str:
    for pattern in _FILE_ID_PATTERNS:
        m = pattern.search(url)
        if m:
            return m.group(1)
    raise ValueError(f"Google Drive file ID not found in URL: {url}")


class DriveDownloader:
    def __init__(self, credentials_path: str) -> None:
        creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
        self._service = build("drive", "v3", credentials=creds)

    def download_images(self, urls: list[str]) -> list[Path]:
        TMP_DIR.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []
        for url in urls:
            file_id = _extract_file_id(url)
            meta = self._service.files().get(fileId=file_id, fields="name,mimeType").execute()
            name = meta.get("name", file_id)
            dest = TMP_DIR / name

            request = self._service.files().get_media(fileId=file_id)
            with open(dest, "wb") as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()

            paths.append(dest)
        return paths

    def cleanup(self, paths: list[Path]) -> None:
        for p in paths:
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass
