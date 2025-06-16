import httpx
from typing import Dict, Optional, List, Any
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.telegram_bot import TelegramBot
from app.models.flow import Flow
from app.services.flow_engine import FlowEngine
from app.schemas.flow import FlowExecutionContext


class TelegramService:
    BASE_URL = "https://api.telegram.org/bot"

    @classmethod
    async def get_bot_info(cls, token: str) -> Dict:
        """
        Fetch bot information from Telegram API using the bot token
        """
        url = f"{cls.BASE_URL}{token}/getMe"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10.0)
            if response.status_code != 200:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid bot token or Telegram API error"
                )
            data = response.json()
            if not data.get("ok"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Telegram API error: {data.get('description', 'Unknown error')}"
                )
            bot_info = data["result"]
            # Validate that this is actually a bot
            if not bot_info.get("is_bot"):
                raise HTTPException(
                    status_code=400,
                    detail="The provided token does not belong to a bot"
                )
            return {
                "id": bot_info["id"],
                "username": bot_info["username"],
                "first_name": bot_info["first_name"],
                "is_bot": bot_info["is_bot"],
                "can_join_groups": bot_info.get("can_join_groups", True),
                "can_read_all_group_messages": bot_info.get("can_read_all_group_messages", False),
                "supports_inline_queries": bot_info.get("supports_inline_queries", False),
                "token": token
            }
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=408,
                detail="Timeout while connecting to Telegram API"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error connecting to Telegram API: {str(e)}"
            )

    @classmethod
    async def get_bot_description(cls, token: str) -> Dict[str, Optional[str]]:
        """
        Fetch bot description from Telegram API
        """
        url = f"{cls.BASE_URL}{token}/getMyDescription"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    result = data.get("result", {})
                    return {
                        "description": result.get("description"),
                    }
            return {"description": None}
        except (httpx.TimeoutException, httpx.RequestError):
            # If we can't get description, it's not critical
            return {"description": None}

    @classmethod
    async def get_bot_short_description(cls, token: str) -> Dict[str, Optional[str]]:
        """
        Fetch bot short description from Telegram API
        """
        url = f"{cls.BASE_URL}{token}/getMyShortDescription"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    result = data.get("result", {})
                    return {
                        "short_description": result.get("short_description"),
                    }
            return {"short_description": None}
        except (httpx.TimeoutException, httpx.RequestError):
            # If we can't get short description, it's not critical
            return {"short_description": None}

    @classmethod
    async def get_full_bot_info(cls, token: str) -> Dict:
        """
        Get complete bot information including descriptions
        """
        # Get basic bot info
        bot_info = await cls.get_bot_info(token)
        # Get descriptions (these are optional and won't fail the entire process)
        description_info = await cls.get_bot_description(token)
        short_description_info = await cls.get_bot_short_description(token)
        # Merge all information
        bot_info.update(description_info)
        bot_info.update(short_description_info)
        return bot_info

    @classmethod
    async def set_webhook(cls, token: str, webhook_url: str) -> bool:
        """
        Set webhook URL for a Telegram bot.

        Args:
            token: Bot token
            webhook_url: URL where Telegram should send updates

        Returns:
            bool: True if webhook was set successfully
        """
        url = f"{cls.BASE_URL}{token}/setWebhook"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json={"url": webhook_url},
                    timeout=10.0
                )

            if response.status_code != 200:
                return False

            data = response.json()
            return data.get("ok", False)

        except (httpx.TimeoutException, httpx.RequestError) as e:
            print(f"Error setting webhook: {e}")
            return False

    @classmethod
    async def get_webhook_info(cls, token: str) -> Dict:
        """
        Get current webhook information for a bot.

        Returns:
            Dict: Webhook info including URL, pending updates, etc.
        """
        url = f"{cls.BASE_URL}{token}/getWebhookInfo"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10.0)

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    return data.get("result", {})

            return {}

        except (httpx.TimeoutException, httpx.RequestError) as e:
            print(f"Error getting webhook info: {e}")
            return {}

    @classmethod
    async def delete_webhook(cls, token: str) -> bool:
        """
        Remove webhook for a bot (switches back to polling mode).
        """
        url = f"{cls.BASE_URL}{token}/deleteWebhook"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, timeout=10.0)

            if response.status_code == 200:
                data = response.json()
                return data.get("ok", False)

            return False

        except (httpx.TimeoutException, httpx.RequestError) as e:
            print(f"Error deleting webhook: {e}")
            return False

    @classmethod
    async def send_message(
            cls,
            token: str,
            chat_id: int,
            text: str,
            quick_replies: Optional[List[str]] = None,
            parse_mode: Optional[str] = None
    ) -> bool:
        """
        Send a message via Telegram bot.

        Args:
            token: Bot token
            chat_id: Telegram chat ID
            text: Message text
            quick_replies: Optional list of quick reply buttons
            parse_mode: Optional parse mode (HTML, Markdown, etc.)

        Returns:
            bool: True if message was sent successfully
        """
        url = f"{cls.BASE_URL}{token}/sendMessage"

        payload = {
            "chat_id": chat_id,
            "text": text
        }

        if parse_mode:
            payload["parse_mode"] = parse_mode

        # Add quick replies as keyboard
        if quick_replies:
            keyboard = [[{"text": reply}] for reply in quick_replies]
            payload["reply_markup"] = {
                "keyboard": keyboard,
                "resize_keyboard": True,
                "one_time_keyboard": True
            }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=payload,
                    timeout=10.0
                )

            return response.status_code == 200

        except (httpx.TimeoutException, httpx.RequestError) as e:
            print(f"Error sending message: {e}")
            return False

    @classmethod
    async def process_telegram_update(
            cls,
            update: Dict[str, Any],
            bot_token: str,
            db: Session
    ) -> Dict[str, Any]:
        """
        Process incoming Telegram update and execute appropriate flow.

        Args:
            update: Telegram update object
            bot_token: Bot token from the webhook URL
            db: Database session

        Returns:
            Dict: Response to send back to Telegram
        """
        try:
            print(f"Processing Telegram update: {update}")

            # Extract message info
            if "message" not in update:
                return {"ok": True}  # Ignore non-message updates

            message = update["message"]
            user_id = message["from"]["id"]
            chat_id = message["chat"]["id"]
            text = message.get("text", "")

            print(f"Message: '{text}' from user {user_id} in chat {chat_id}")

            # Find the bot by token
            bot = TelegramBot.get_by_token(db, bot_token)
            if not bot:
                print(f"Bot not found for token: {bot_token[:10]}...")
                return {"ok": False}

            print(f"Found bot: {bot.username}")

            # Check if bot is active
            if not bot.is_active:
                return {
                    "method": "sendMessage",
                    "chat_id": chat_id,
                    "text": f"🤖 {bot.first_name} is currently inactive. Please try again later."
                }

            # Find default flow for this bot
            default_flow = Flow.get_default_flow(db, bot.id)
            if not default_flow:
                return {
                    "method": "sendMessage",
                    "chat_id": chat_id,
                    "text": f"👋 Hello! I'm {bot.first_name}. I'm still being configured with conversation flows."
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
                    "first_name": message["from"].get("first_name"),
                    "last_name": message["from"].get("last_name"),
                    "language_code": message["from"].get("language_code")
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
                    error_msg = result.error_message or "I didn't understand that. Could you try again?"
                    return {
                        "method": "sendMessage",
                        "chat_id": chat_id,
                        "text": f"🤔 {error_msg}"
                    }

            finally:
                await engine.close()

        except Exception as e:
            print(f"Error processing Telegram update: {e}")
            import traceback
            traceback.print_exc()

            # Return a generic error message to the user
            return {
                "method": "sendMessage",
                "chat_id": update.get("message", {}).get("chat", {}).get("id"),
                "text": "⚠️ Sorry, I encountered an error. Please try again later."
            }

    @classmethod
    async def test_flow_execution(
            cls,
            bot_token: str,
            test_message: str,
            db: Session
    ) -> Dict[str, Any]:
        """
        Test flow execution without going through Telegram.

        Args:
            bot_token: Bot token
            test_message: Test message to send
            db: Database session

        Returns:
            Dict: Test result with bot response
        """
        try:
            # Find the bot
            bot = TelegramBot.get_by_token(db, bot_token)
            if not bot:
                return {"error": "Bot not found"}

            # Find default flow
            default_flow = Flow.get_default_flow(db, bot.id)
            if not default_flow:
                return {"error": "No default flow configured for this bot"}

            # Create test context
            from datetime import datetime
            context = FlowExecutionContext(
                user_id="test_user",
                session_id=f"test_{int(datetime.now().timestamp())}",
                variables={"test_mode": True}
            )

            # Execute flow
            engine = FlowEngine(db)
            try:
                result = await engine.execute_flow(default_flow.id, test_message, context)
                return {
                    "success": result.success,
                    "input_message": test_message,
                    "bot_response": result.response_message,
                    "quick_replies": result.quick_replies,
                    "variables_updated": result.variables_updated,
                    "actions_performed": result.actions_performed,
                    "next_node": result.next_node_id,
                    "error": result.error_message
                }
            finally:
                await engine.close()

        except Exception as e:
            print(f"Error testing flow: {e}")
            return {"error": str(e)}

    @classmethod
    async def setup_bot_automatically(cls, bot_token: str, bot_id: int) -> Dict[str, Any]:
        """
        Automatically set up webhook for a bot when it's created.
        This is called when a user adds a bot token.
        """
        from app.core.config import settings

        try:
            # Construct the webhook URL automatically
            webhook_url = f"{settings.WEBHOOK_BASE_URL}/api/v1/telegram/webhook/{bot_token}"

            print(f"Setting up automatic webhook: {webhook_url}")

            # Set the webhook with Telegram
            success = await cls.set_webhook(bot_token, webhook_url)

            if success:
                return {
                    "success": True,
                    "webhook_url": webhook_url,
                    "message": "Bot configured successfully! Ready to receive messages."
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to configure webhook with Telegram"
                }

        except Exception as e:
            print(f"Error in automatic setup: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    @classmethod
    async def verify_webhook_setup(cls, bot_token: str) -> Dict[str, Any]:
        """
        Verify that webhook is properly configured.
        """
        try:
            webhook_info = await cls.get_webhook_info(bot_token)
            from app.core.config import settings

            expected_url = f"{settings.WEBHOOK_BASE_URL}/api/v1/telegram/webhook/{bot_token}"
            current_url = webhook_info.get("url", "")

            return {
                "is_configured": bool(current_url),
                "is_correct": current_url == expected_url,
                "current_url": current_url,
                "expected_url": expected_url,
                "webhook_info": webhook_info
            }

        except Exception as e:
            return {
                "is_configured": False,
                "is_correct": False,
                "error": str(e)
            }
