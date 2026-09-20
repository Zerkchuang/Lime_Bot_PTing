"""集中管理環境變數設定"""
import os
from dataclasses import dataclass


@dataclass
class Settings:
    LINE_CHANNEL_ACCESS_TOKEN: str = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    LINE_CHANNEL_SECRET: str = os.environ.get("LINE_CHANNEL_SECRET", "")
    ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL: str = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    # 對話記憶保留的最大輪數（每個使用者），避免 context 無限增長
    MAX_HISTORY_TURNS: int = int(os.environ.get("MAX_HISTORY_TURNS", "10"))

    # --- Google Drive 持久化儲存（選用）---
    # 兩個都有填才會啟用 Drive 儲存，否則自動退回記憶體版（見 app/storage/__init__.py）
    # GOOGLE_SERVICE_ACCOUNT_JSON：整包 service account JSON 金鑰內容（不是路徑，是內容字串）
    GOOGLE_SERVICE_ACCOUNT_JSON: str = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    # GOOGLE_DRIVE_FOLDER_ID：要把對話記錄存進哪個資料夾，從資料夾網址取得
    GOOGLE_DRIVE_FOLDER_ID: str = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "")

    def validate(self):
        missing = [
            k
            for k in ["LINE_CHANNEL_ACCESS_TOKEN", "LINE_CHANNEL_SECRET", "ANTHROPIC_API_KEY"]
            if not getattr(self, k)
        ]
        if missing:
            raise RuntimeError(f"缺少必要環境變數: {', '.join(missing)}")


settings = Settings()
