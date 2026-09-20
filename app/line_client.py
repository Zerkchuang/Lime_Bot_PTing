"""LINE Messaging API 的簡易封裝"""
import httpx
import logging

logger = logging.getLogger("line-bot.client")

LINE_API_BASE = "https://api.line.me/v2/bot"


class LineClient:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }

    async def reply_text(self, reply_token: str, text: str):
        """用 replyToken 回覆訊息，僅能用一次且約 1 分鐘內有效"""
        # LINE 單則文字上限 5000 字，超長訊息自動切段
        chunks = [text[i : i + 4900] for i in range(0, len(text), 4900)] or [""]
        messages = [{"type": "text", "text": c} for c in chunks[:5]]  # reply 最多 5 則
        payload = {"replyToken": reply_token, "messages": messages}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{LINE_API_BASE}/message/reply", headers=self.headers, json=payload
            )
            if resp.status_code != 200:
                logger.error(f"reply 失敗: {resp.status_code} {resp.text}")

    async def push_text(self, user_id: str, text: str):
        """主動推播訊息給指定使用者（用於通知、排程提醒等），計入月配額"""
        chunks = [text[i : i + 4900] for i in range(0, len(text), 4900)] or [""]
        messages = [{"type": "text", "text": c} for c in chunks[:5]]
        payload = {"to": user_id, "messages": messages}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{LINE_API_BASE}/message/push", headers=self.headers, json=payload
            )
            if resp.status_code != 200:
                logger.error(f"push 失敗: {resp.status_code} {resp.text}")
