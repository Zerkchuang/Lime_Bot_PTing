"""
文字訊息處理邏輯：
- 開頭是 "/" 的視為指令（可擴充，例如日後接股價查詢、提醒事項等）
- 其他一律丟給 Claude 做智能對話，並維護每個使用者的對話歷史
"""
from app import storage
from app.claude_client import get_claude_reply

HELP_TEXT = (
    "📋 目前支援的指令：\n"
    "/help - 顯示這個說明\n"
    "/clear - 清除目前的對話記憶，重新開始\n"
    "\n"
    "其他訊息我都會用 AI 回覆你，可以直接問問題、聊天、"
    "請我幫忙寫東西或分析事情。\n"
    "\n"
    "（之後可以在 handlers.py 裡新增指令，例如串接股價查詢、"
    "提醒事項、資料庫查詢等功能）"
)


async def handle_text_message(line_client, reply_token: str, user_id: str, user_text: str):
    text = user_text.strip()

    # --- 指令路由：在這裡新增更多 "/xxx" 指令即可擴充功能 ---
    if text == "/help":
        await line_client.reply_text(reply_token, HELP_TEXT)
        return

    if text == "/clear":
        await storage.clear(user_id)
        await line_client.reply_text(reply_token, "已清除對話記憶，我們重新開始吧。")
        return

    # --- 預設行為：呼叫 Claude 進行智能對話 ---
    history = await storage.get_history(user_id)
    reply = await get_claude_reply(history, text)

    await storage.append(user_id, "user", text)
    await storage.append(user_id, "assistant", reply)

    await line_client.reply_text(reply_token, reply)
