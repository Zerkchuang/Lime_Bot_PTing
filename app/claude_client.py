"""Anthropic Claude API 封裝，負責產生智能回覆"""
import httpx
import logging
from app.config import settings

logger = logging.getLogger("line-bot.claude")

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

SYSTEM_PROMPT = (
    "你是一個透過 LINE 提供服務的萬能助理，個性務實、簡潔、有幫助。"
    "回覆請用繁體中文，避免過長的鋪陳，直接給重點。"
    "如果使用者的問題需要即時資料（例如股價、天氣、新聞），"
    "請誠實說明你目前沒有即時查詢能力，而不是編造答案。"
)


async def get_claude_reply(history: list[dict], user_text: str) -> str:
    """
    history: [{"role": "user"/"assistant", "content": "..."}]
    回傳純文字回覆
    """
    messages = history + [{"role": "user", "content": user_text}]
    payload = {
        "model": settings.CLAUDE_MODEL,
        "max_tokens": 1024,
        "system": SYSTEM_PROMPT,
        "messages": messages,
    }
    headers = {
        "x-api-key": settings.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(ANTHROPIC_API_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
            return "\n".join(text_blocks).strip() or "（沒有取得回覆內容）"
        except httpx.HTTPStatusError as e:
            logger.error(f"Claude API 錯誤: {e.response.status_code} {e.response.text}")
            return "抱歉，AI 服務暫時出了點問題，請稍後再試一次。"
        except Exception:
            logger.exception("呼叫 Claude API 失敗")
            return "抱歉，處理你的訊息時發生錯誤。"
