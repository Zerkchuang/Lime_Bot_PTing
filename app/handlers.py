"""
文字訊息處理邏輯：
- 開頭是 "/" 的視為指令
- 其他一律丟給 Claude 做智能對話，並維護每個使用者的對話歷史
"""
from app import storage
from app.claude_client import get_claude_reply
from app.apis import get_stock_quote, get_news, get_weather

HELP_TEXT = (
    "📋 目前支援的指令：\n"
    "/help - 顯示這個說明\n"
    "/clear - 清除目前的對話記憶，重新開始\n"
    "/stock 代號 - 查股價，例如 /stock 6446\n"
    "/news 關鍵字 - 查新聞，例如 /news 藥華藥\n"
    "/weather 地名 - 查天氣，例如 /weather 台南\n"
    "\n"
    "其他訊息我都會用 AI 回覆你，可以直接問問題、聊天、"
    "請我幫忙寫東西或分析事情。"
)


async def handle_text_message(line_client, reply_token: str, user_id: str, user_text: str):
    text = user_text.strip()

    if text == "/help":
        await line_client.reply_text(reply_token, HELP_TEXT)
        return

    if text == "/clear":
        await storage.clear(user_id)
        await line_client.reply_text(reply_token, "已清除對話記憶，我們重新開始吧。")
        return

    if text.startswith("/stock"):
        arg = text[len("/stock"):].strip()
        if not arg:
            await line_client.reply_text(reply_token, "請提供股票代號，例如 /stock 6446")
            return
        reply = await get_stock_quote(arg)
        await line_client.reply_text(reply_token, reply)
        return

    if text.startswith("/news"):
        arg = text[len("/news"):].strip()
        if not arg:
            await line_client.reply_text(reply_token, "請提供搜尋關鍵字，例如 /news 藥華藥")
            return
        reply = await get_news(arg)
        await line_client.reply_text(reply_token, reply)
        return

    if text.startswith("/weather"):
        arg = text[len("/weather"):].strip()
        if not arg:
            await line_client.reply_text(reply_token, "請提供地名，例如 /weather 台南")
            return
        reply = await get_weather(arg)
        await line_client.reply_text(reply_token, reply)
        return

    history = await storage.get_history(user_id)
    reply = await get_claude_reply(history, text)

    await storage.append(user_id, "user", text)
    await storage.append(user_id, "assistant", reply)

    await line_client.reply_text(reply_token, reply)
