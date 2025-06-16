from urllib.parse import unquote

from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.telegram_bot import TelegramBot
from app.models.flow import Flow
from app.services.flow_engine import FlowEngine
from app.schemas.flow import FlowExecutionContext

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

        # Extract message info
        if "message" not in update:
            return {"ok": True}

        message = update["message"]
        user_id = message["from"]["id"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "")
        bot_token = unquote(bot_token)
        print(bot_token)

        # Find the bot by token
        bot = TelegramBot.get_by_token(db, bot_token)
        if not bot:
            print(f"Bot not found for token: {bot_token}")
            return {"ok": False}

        print(f"Found bot: {bot.username} for message: {text}")

        # Find default flow for this bot
        default_flow = Flow.get_default_flow(db, bot.id)
        if not default_flow:
            # No flow configured - send default message
            return {
                "method": "sendMessage",
                "chat_id": chat_id,
                "text": f"Hello! I'm {bot.first_name}. I'm still being configured with conversation flows."
            }

        print(f"Executing flow: {default_flow.name}")

        # Create execution context
        session_id = f"tg_{chat_id}_{user_id}"
        context = FlowExecutionContext(
            user_id=str(user_id),
            session_id=session_id,
            variables={
                "chat_id": chat_id,
                "username": message["from"].get("username"),
                "first_name": message["from"].get("first_name")
            }
        )

        # Execute the flow
        engine = FlowEngine(db)
        try:
            result = await engine.execute_flow(default_flow.id, text, context)

            if result.success and result.response_message:
                response = {
                    "method": "sendMessage",
                    "chat_id": chat_id,
                    "text": result.response_message
                }

                # Add quick replies if available
                if result.quick_replies:
                    keyboard = [[{"text": reply}] for reply in result.quick_replies]
                    response["reply_markup"] = {
                        "keyboard": keyboard,
                        "resize_keyboard": True,
                        "one_time_keyboard": True
                    }

                print(f"Sending response: {result.response_message}")
                return response
            else:
                return {
                    "method": "sendMessage",
                    "chat_id": chat_id,
                    "text": "I didn't understand that. Could you try again?"
                }

        finally:
            await engine.close()

    except Exception as e:
        print(f"Telegram webhook error: {e}")
        import traceback
        traceback.print_exc()
        return {"ok": False}