"""
Google Drive connector using service-account JSON key authentication.
"""
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

from app.config.settings import get_settings

settings = get_settings()

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
SUPPORTED_MIME_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "text/plain": "txt",
    "image/png": "png",
    "image/jpeg": "jpeg",
    "image/jpg": "jpg",
}


def _get_service():
    creds = service_account.Credentials.from_service_account_file(
        settings.google_credentials_path, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)


def list_drive_files(folder_id: str | None = None) -> list[dict]:
    """List all supported files in a Drive folder (or root if None)."""
    service = _get_service()
    query = " or ".join(f"mimeType='{m}'" for m in SUPPORTED_MIME_TYPES)
    if folder_id:
        query = f"({query}) and '{folder_id}' in parents and trashed=false"

    results = service.files().list(
        q=query,
        fields="files(id, name, mimeType, size, modifiedTime, parents)",
        pageSize=100,
    ).execute()

    files = []
    for f in results.get("files", []):
        files.append({
            "drive_file_id": f["id"],
            "name": f["name"],
            "file_type": SUPPORTED_MIME_TYPES.get(f["mimeType"], "unknown"),
            "size": int(f.get("size", 0)),
            "modified_at": f.get("modifiedTime"),
        })
    return files


def download_drive_file(file_id: str, dest_path: str) -> int:
    """Download a Drive file to dest_path. Returns file size in bytes."""
    service = _get_service()
    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    content = buf.getvalue()
    Path(dest_path).write_bytes(content)
    return len(content)
