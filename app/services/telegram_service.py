from typing import Dict, Optional, List, Any
from fastapi import HTTPException
from sqlalchemy.orm import Session
from telegram import Bot, Update
from telegram.ext import Application
from telegram.error import TelegramError, InvalidToken

from app.models.telegram_bot import TelegramBot
from app.models.telegram_chat import TelegramChat
from app.models.chat_user_message_count import ChatUserMessageCount
from app.models.flow import Flow, FlowSession
from app.services.flow_engine import FlowEngine
from app.schemas.flow import FlowExecutionContext


class TelegramService:
    """
    Service for handling Telegram bot operations using python-telegram-bot library.
    """

    @classmethod
    async def get_bot_info(cls, token: str) -> Dict:
        """
        Fetch bot information from Telegram API using the bot token
        """
        try:
            bot = Bot(token)
            bot_info = await bot.get_me()
            
            return {
                "id": bot_info.id,
                "username": bot_info.username,
                "first_name": bot_info.first_name,
                "is_bot": bot_info.is_bot,
                "can_join_groups": bot_info.can_join_groups,
                "can_read_all_group_messages": bot_info.can_read_all_group_messages,
                "supports_inline_queries": bot_info.supports_inline_queries,
                "token": token
            }
        except InvalidToken:
            raise HTTPException(
                status_code=400,
                detail="Invalid bot token"
            )
        except TelegramError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Telegram API error: {str(e)}"
            )

    @classmethod
    async def get_bot_description(cls, token: str) -> Dict[str, Optional[str]]:
        """
        Fetch bot description from Telegram API
        """
        try:
            bot = Bot(token)
            bot_info = await bot.get_my_description()
            return {
                "description": bot_info.description,
            }
        except TelegramError:
            # If we can't get description, it's not critical
            return {"description": None}

    @classmethod
    async def get_bot_short_description(cls, token: str) -> Dict[str, Optional[str]]:
        """
        Fetch bot short description from Telegram API
        """
        try:
            bot = Bot(token)
            bot_info = await bot.get_my_short_description()
            return {
                "short_description": bot_info.short_description,
            }
        except TelegramError:
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
        try:
            bot = Bot(token)
            result = await bot.set_webhook(url=webhook_url)
            return result
        except TelegramError as e:
            print(f"Error setting webhook: {e}")
            return False

    @classmethod
    async def get_webhook_info(cls, token: str) -> Dict:
        """
        Get current webhook information for a bot.

        Returns:
            Dict: Webhook info including URL, pending updates, etc.
        """
        try:
            bot = Bot(token)
            webhook_info = await bot.get_webhook_info()
            return {
                "url": webhook_info.url,
                "has_custom_certificate": webhook_info.has_custom_certificate,
                "pending_update_count": webhook_info.pending_update_count,
                "ip_address": webhook_info.ip_address,
                "last_error_date": webhook_info.last_error_date.isoformat() if webhook_info.last_error_date else None,
                "last_error_message": webhook_info.last_error_message,
                "max_connections": webhook_info.max_connections,
                "allowed_updates": webhook_info.allowed_updates
            }
        except TelegramError as e:
            print(f"Error getting webhook info: {e}")
            return {}

    @classmethod
    async def delete_webhook(cls, token: str) -> bool:
        """
        Remove webhook for a bot (switches back to polling mode).
        """
        try:
            bot = Bot(token)
            result = await bot.delete_webhook()
            return result
        except TelegramError as e:
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
        try:
            bot = Bot(token)
            
            # Prepare reply markup if quick replies are provided
            reply_markup = None
            if quick_replies:
                from telegram import ReplyKeyboardMarkup, KeyboardButton
                keyboard = [[KeyboardButton(reply)] for reply in quick_replies]
                reply_markup = ReplyKeyboardMarkup(
                    keyboard,
                    resize_keyboard=True,
                    one_time_keyboard=True
                )

            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
            return True

        except TelegramError as e:
            print(f"Error sending message: {e}")
            return False

    @classmethod
    async def process_update(
            cls,
            update: Dict[str, Any],
            bot_token: str,
            db: Session
    ) -> Dict[str, Any]:
        """
        Process a Telegram update and execute the appropriate flow.
        """
        try:
            # Parse the update using python-telegram-bot
            telegram_update = Update.de_json(update, Bot(bot_token))
            
            # Extract message info
            if not telegram_update.message:
                return {"ok": True}

            message = telegram_update.message
            user_id = message.from_user.id
            chat_id = message.chat.id
            text = message.text or ""

            # Update or create TelegramChat record
            chat_data = {
                "telegram_id": chat_id,
                "type": message.chat.type,
                "title": message.chat.title
            }
            existing_chat = TelegramChat.get_by_id(db, chat_id)
            if not existing_chat:
                TelegramChat.create(db, chat_data)
            else:
                # Update chat info if it has changed
                TelegramChat.update(db, chat_id, chat_data)

            # Create or get user record first
            from app.models.user import User
            existing_user = User.get_by_telegram_id(db, str(user_id))
            if not existing_user:
                # Create a basic user record for this Telegram user
                from app.schemas.user import UserCreate
                user_create = UserCreate(
                    username=message.from_user.username or f"user_{user_id}",
                    telegram_id=str(user_id),
                    telegram_username=message.from_user.username or "",
                    first_name=message.from_user.first_name,
                    last_name=message.from_user.last_name,
                    is_active=True
                )
                existing_user = User.create(db, user_create)

            # Update message count for this user in this chat
            message_count_record = ChatUserMessageCount.get_by_id(db, chat_id, existing_user.id)
            if message_count_record:
                # Increment message count
                ChatUserMessageCount.update(db, chat_id, existing_user.id, {
                    "message_count": message_count_record.message_count + 1
                })
            else:
                # Create new record with count of 1
                ChatUserMessageCount.create(db, {
                    "chat_id": chat_id,
                    "user_id": existing_user.id,
                    "message_count": 1
                })

            # Find the bot by token
            bot = TelegramBot.get_by_token(db, bot_token)
            if not bot:
                return {"ok": False}

            # Upsert BotUser association for this user and bot
            from app.models.bot_user import BotUser
            BotUser.get_or_create(db, bot_id=bot.id, user_id=existing_user.id, telegram_user_id=str(user_id))

            # If bot is not active, don't execute flow
            if not bot.is_active:
                return {"ok": True}

            # Find default flow for this bot
            default_flow = Flow.get_default_flow(db, bot.id)
            if not default_flow:
                # No flow configured - send default message
                return {
                    "method": "sendMessage",
                    "chat_id": chat_id,
                    "text": f"Hello! I'm {bot.first_name}. I'm still being configured with conversation flows."
                }

            # Create execution context
            session_id = f"tg_{chat_id}_{user_id}"
            # Load session state
            flow_session = FlowSession.get_by_session(db, str(user_id), bot.id, session_id)
            
            # Reset session if user sends /start or other restart commands
            should_reset = text.lower().strip() in ['/start', '/restart', '/reset']
            if should_reset:
                current_node_id = None
                variables = {
                    "chat_id": chat_id,
                    "username": message.from_user.username,
                    "first_name": message.from_user.first_name
                }
            else:
                current_node_id = flow_session.current_node_id if flow_session else None
                variables = flow_session.variables if flow_session and flow_session.variables else {
                    "chat_id": chat_id,
                    "username": message.from_user.username,
                    "first_name": message.from_user.first_name
                }
            
            context = FlowExecutionContext(
                bot_id=bot.bot_id,
                user_id=str(user_id),
                chat_id=str(chat_id),
                session_id=session_id,
                current_node_id=current_node_id,
                variables=variables
            )

            # Execute the flow
            engine = FlowEngine(db)
            try:
                result = await engine.execute_flow(default_flow.id, text, context)

                if result.success:
                    # Save session state
                    FlowSession.create_or_update(
                        db,
                        str(user_id),
                        bot.id,
                        session_id,
                        context.current_node_id,
                        context.variables
                    )
                    if result.response_message:
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

                        return response

                else:
                    error_msg = f"Flow execution failed: {result.error_message}"
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



    @classmethod
    async def setup_bot_automatically(cls, bot_token: str, bot_id: int) -> Dict[str, Any]:
        """
        Automatically setup a bot with webhook and basic configuration.
        """
        try:
            # Get bot info
            bot_info = await cls.get_bot_info(bot_token)
            
            # Set webhook (assuming the webhook URL is configured in settings)
            from app.core.config import settings
            webhook_url = f"{settings.BASE_URL}/api/v1/telegram/webhook/{bot_token}"
            
            webhook_success = await cls.set_webhook(bot_token, webhook_url)
            
            return {
                "success": True,
                "bot_info": bot_info,
                "webhook_set": webhook_success,
                "webhook_url": webhook_url
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    @classmethod
    async def ban_chat_member(
            cls,
            token: str,
            chat_id: int,
            user_id: int,
            until_date: Optional[int] = None,
            revoke_messages: bool = False
    ) -> Dict[str, Any]:
        """
        Ban a member from a chat.

        Args:
            token: Bot token
            chat_id: Telegram chat ID
            user_id: Telegram user ID to ban
            until_date: Optional timestamp until when the user is banned (None for permanent ban)
            revoke_messages: Whether to delete all messages from the user

        Returns:
            Dict: Result with success status and details
        """
        try:
            bot = Bot(token)
            result = await bot.ban_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                until_date=until_date,
                revoke_messages=revoke_messages
            )
            
            return {
                "success": True,
                "result": result,
                "message": f"User {user_id} has been banned from chat {chat_id}"
            }
            
        except TelegramError as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to ban user {user_id} from chat {chat_id}"
            }

    @classmethod
    async def unban_chat_member(
            cls,
            token: str,
            chat_id: int,
            user_id: int,
            only_if_banned: bool = True
    ) -> Dict[str, Any]:
        """
        Unban a member from a chat.

        Args:
            token: Bot token
            chat_id: Telegram chat ID
            user_id: Telegram user ID to unban
            only_if_banned: If True, only unban if the user is currently banned

        Returns:
            Dict: Result with success status and details
        """
        try:
            bot = Bot(token)
            result = await bot.unban_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                only_if_banned=only_if_banned
            )
            
            return {
                "success": True,
                "result": result,
                "message": f"User {user_id} has been unbanned from chat {chat_id}"
            }
            
        except TelegramError as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to unban user {user_id} from chat {chat_id}"
            }

    @classmethod
    async def verify_webhook_setup(cls, bot_token: str) -> Dict[str, Any]:
        """
        Verify that the webhook is properly configured for a bot, returning legacy keys for compatibility.
        """
        try:
            from app.core.config import settings
            webhook_info = await cls.get_webhook_info(bot_token)
            expected_url = f"{settings.BASE_URL}/api/v1/telegram/webhook/{bot_token}"
            current_url = webhook_info.get("url", "")
            is_configured = bool(current_url)
            is_correct = current_url == expected_url
            return {
                "is_configured": is_configured,
                "is_correct": is_correct,
                "current_url": current_url,
                "expected_url": expected_url,
                "webhook_info": webhook_info
            }
        except Exception as e:
            return {
                "is_configured": False,
                "is_correct": False,
                "current_url": None,
                "expected_url": None,
                "webhook_info": {},
                "error": str(e)
            }
