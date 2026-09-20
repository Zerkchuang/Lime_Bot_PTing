"""
LINE 萬能助理 Bot - 主程式
負責接收 LINE Webhook、驗證簽章、分派事件處理
"""
import hashlib
import hmac
import base64
import logging
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from app.config import settings
from app.line_client import LineClient
from app.handlers import handle_text_message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("line-bot")

app = FastAPI(title="LINE 萬能助理")
line_client = LineClient(settings.LINE_CHANNEL_ACCESS_TOKEN)


def verify_signature(body: bytes, signature: str) -> bool:
    """驗證 LINE Webhook 簽章，避免偽造請求"""
    hash_ = hmac.new(
        settings.LINE_CHANNEL_SECRET.encode("utf-8"),
        body,
        hashlib.sha256,
    ).digest()
    expected_signature = base64.b64encode(hash_).decode("utf-8")
    return hmac.compare_digest(expected_signature, signature)


@app.get("/")
async def health_check():
    """健康檢查端點，部署平台常用來確認服務存活"""
    return {"status": "ok", "service": "line-bot"}


@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()
    signature = request.headers.get("X-Line-Signature", "")

    if not signature or not verify_signature(body, signature):
        logger.warning("簽章驗證失敗，拒絕請求")
        raise HTTPException(status_code=400, detail="Invalid signature")

    payload = await request.json()
    events = payload.get("events", [])

    # LINE 要求盡快回 200，耗時處理丟到背景任務執行
    for event in events:
        background_tasks.add_task(dispatch_event, event)

    return JSONResponse(content={"status": "received"})


async def dispatch_event(event: dict):
    """依事件類型分派處理，目前僅處理文字訊息，可依需求擴充"""
    try:
        event_type = event.get("type")
        reply_token = event.get("replyToken")
        source = event.get("source", {})
        user_id = source.get("userId")

        if event_type == "message":
            message = event.get("message", {})
            if message.get("type") == "text":
                user_text = message.get("text", "")
                await handle_text_message(
                    line_client=line_client,
                    reply_token=reply_token,
                    user_id=user_id,
                    user_text=user_text,
                )
            else:
                # 貼圖、圖片、位置等非文字訊息，先給預設回覆
                await line_client.reply_text(
                    reply_token, "目前只支援文字訊息，其他類型還在開發中喔。"
                )

        elif event_type == "follow":
            # 使用者加好友時的歡迎訊息
            await line_client.reply_text(
                reply_token,
                "嗨，我是你的萬能助理！直接傳訊息給我就可以開始對話，"
                "輸入「/help」查看目前支援的功能。",
            )

        elif event_type == "postback":
            # Rich Menu 或 Flex Message 按鈕觸發的事件，預留擴充點
            data = event.get("postback", {}).get("data", "")
            logger.info(f"收到 postback: {data}")

    except Exception:
        logger.exception("處理事件時發生錯誤")
