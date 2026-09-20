"""
使用 Google Drive 作為對話歷史的持久化儲存

架構：
- 用 Google Service Account（機器對機器的授權方式）存取 Drive，
  因為 bot 是無人值守跑在伺服器上的程式，沒辦法跳出瀏覽器讓你用個人帳號登入
- 在你指定的 Drive 資料夾（GOOGLE_DRIVE_FOLDER_ID）底下，
  每個使用者一個檔案：conv_<user_id>.json
- 為了不讓每則訊息都要等 Drive API 往返造成延遲，
  用記憶體做快取：同一個 process 存活期間，只有「第一次看到這個使用者」
  或「這個使用者有新訊息要寫入」時才會打 Drive API
- googleapiclient 是同步 (blocking) 的函式庫，所以用 asyncio.to_thread
  丟到背景執行緒跑，避免卡住 FastAPI 的 event loop
"""
import json
import asyncio
import logging
from io import BytesIO
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from app.config import settings

logger = logging.getLogger("line-bot.drive")

SCOPES = ["https://www.googleapis.com/auth/drive"]

_cache: dict[str, list[dict]] = {}
_file_id_cache: dict[str, str] = {}
_drive_service = None


def _get_service():
    global _drive_service
    if _drive_service is None:
        creds_info = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
        credentials = service_account.Credentials.from_service_account_info(
            creds_info, scopes=SCOPES
        )
        _drive_service = build("drive", "v3", credentials=credentials)
    return _drive_service


def _find_file_sync(user_id: str):
    service = _get_service()
    filename = f"conv_{user_id}.json"
    query = (
        f"name = '{filename}' and '{settings.GOOGLE_DRIVE_FOLDER_ID}' in parents "
        f"and trashed = false"
    )
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    return files[0]["id"] if files else None


def _create_file_sync(user_id: str, content: list) -> str:
    service = _get_service()
    filename = f"conv_{user_id}.json"
    file_metadata = {"name": filename, "parents": [settings.GOOGLE_DRIVE_FOLDER_ID]}
    media = MediaIoBaseUpload(
        BytesIO(json.dumps(content, ensure_ascii=False).encode("utf-8")),
        mimetype="application/json",
    )
    file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    return file["id"]


def _download_file_sync(file_id: str) -> list:
    service = _get_service()
    request = service.files().get_media(fileId=file_id)
    buf = BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    buf.seek(0)
    try:
        return json.loads(buf.read().decode("utf-8"))
    except json.JSONDecodeError:
        return []


def _update_file_sync(file_id: str, content: list):
    service = _get_service()
    media = MediaIoBaseUpload(
        BytesIO(json.dumps(content, ensure_ascii=False).encode("utf-8")),
        mimetype="application/json",
    )
    service.files().update(fileId=file_id, media_body=media).execute()


def _delete_file_sync(file_id: str):
    service = _get_service()
    service.files().delete(fileId=file_id).execute()


async def _ensure_loaded(user_id: str):
    if user_id in _cache:
        return
    try:
        file_id = await asyncio.to_thread(_find_file_sync, user_id)
    except Exception:
        logger.exception("查詢 Drive 檔案失敗，先以空對話歷史繼續")
        _cache[user_id] = []
        return
    if file_id:
        _file_id_cache[user_id] = file_id
        try:
            _cache[user_id] = await asyncio.to_thread(_download_file_sync, file_id)
        except Exception:
            logger.exception("下載 Drive 檔案失敗，先以空對話歷史繼續")
            _cache[user_id] = []
    else:
        _cache[user_id] = []


async def get_history(user_id: str) -> list[dict]:
    await _ensure_loaded(user_id)
    max_items = settings.MAX_HISTORY_TURNS * 2
    return _cache[user_id][-max_items:]


async def append(user_id: str, role: str, content: str):
    await _ensure_loaded(user_id)
    _cache[user_id].append({"role": role, "content": content})
    await _persist(user_id)


async def clear(user_id: str):
    await _ensure_loaded(user_id)
    _cache[user_id] = []
    file_id = _file_id_cache.get(user_id)
    if file_id:
        try:
            await asyncio.to_thread(_delete_file_sync, file_id)
        except Exception:
            logger.exception("刪除 Drive 檔案失敗")
        del _file_id_cache[user_id]


async def _persist(user_id: str):
    content = _cache[user_id]
    file_id = _file_id_cache.get(user_id)
    try:
        if file_id:
            await asyncio.to_thread(_update_file_sync, file_id, content)
        else:
            file_id = await asyncio.to_thread(_create_file_sync, user_id, content)
            _file_id_cache[user_id] = file_id
    except Exception:
        # 寫入失敗不影響當次回覆，只是這輪對話沒被存到 Drive，記錄 log 供事後排查
        logger.exception("寫入 Drive 失敗，本輪對話僅存在記憶體快取中")
