from urllib.parse import unquote

from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.telegram_bot import TelegramBot
from app.models.flow import Flow
from app.services.flow_engine import FlowEngine
from app.schemas.flow import FlowExecutionContext
from app.services.telegram_service import TelegramService

router = APIRouter()


@router.post("/telegram/webhook/{bot_token}")
async def telegram_webhook(
        bot_token: str,
        request: Request,
        db: Session = Depends(get_db)
):
    """
    Webhook endpoint for Telegram bot updates.

    To set this up:
    1. Create a bot with @BotFather on Telegram
    2. Set webhook: https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://yourdomain.com/api/v1/telegram/webhook/<TOKEN>
    """
    try:
        update = await request.json()
        print(f"Telegram webhook received: {update}")

        # Decode the bot token from URL
        bot_token = unquote(bot_token)
        print(f"Processing webhook for bot token: {bot_token}")

        result = await TelegramService.process_update(update, bot_token, db)
        
        return result

    except Exception as e:
        print(f"Telegram webhook error: {e}")
        import traceback
        traceback.print_exc()
        return {"ok": False}