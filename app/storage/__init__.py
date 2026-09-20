"""
儲存後端選擇器

有設定 GOOGLE_SERVICE_ACCOUNT_JSON + GOOGLE_DRIVE_FOLDER_ID 時
自動使用 Google Drive 版（跨重啟保留資料）；
沒設定時退回記憶體版（不用任何設定就能跑，但重啟會清空）。

handlers.py 只需要 `from app import storage` 然後呼叫
storage.get_history / storage.append / storage.clear，
完全不用管背後是哪個實作。
"""
import logging
from app.config import settings

logger = logging.getLogger("line-bot.storage")

if settings.GOOGLE_SERVICE_ACCOUNT_JSON and settings.GOOGLE_DRIVE_FOLDER_ID:
    logger.info("對話儲存後端：Google Drive")
    from app.storage.drive_store import get_history, append, clear
else:
    logger.info("對話儲存後端：記憶體（未設定 Google Drive，重啟服務會清空對話記錄）")
    from app.storage.memory_store import get_history, append, clear

__all__ = ["get_history", "append", "clear"]
