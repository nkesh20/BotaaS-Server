import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.bot_user import BotUser
from app.models.telegram_bot import TelegramBot
from app.services.telegram_service import TelegramService
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

def render_template(text: str, user) -> str:
    return (
        text.replace("{{first_name}}", user.first_name or "")
            .replace("{{last_name}}", user.last_name or "")
            .replace("{{telegram_username}}", user.telegram_username or "")
    )

class BroadcastManager:
    def __init__(self):
        self.queues = {}  # bot_id -> asyncio.Queue
        self.workers = {}  # bot_id -> worker task

    def get_queue(self, bot_id: int):
        if bot_id not in self.queues:
            self.queues[bot_id] = asyncio.Queue()
            self.workers[bot_id] = asyncio.create_task(self.worker(bot_id))
        return self.queues[bot_id]

    async def worker(self, bot_id: int):
        queue = self.queues[bot_id]
        while True:
            msg = await queue.get()
            await self.send_broadcast_message(**msg)
            await asyncio.sleep(1/30)  # 30 messages/sec rate limit

    async def send_broadcast_message(self, bot_token: str, chat_id: int, text: str, parse_mode: Optional[str] = None):
        await TelegramService.send_message(
            token=bot_token,
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode
        )

    async def schedule_broadcast(self, db: Session, bot_id: int, text: str, scheduled_time: Optional[datetime] = None, parse_mode: Optional[str] = None):
        bot = TelegramBot.get_by_id(db, bot_id)
        if not bot:
            raise ValueError("Bot not found")
        users = db.query(BotUser).filter_by(bot_id=bot_id, can_receive_broadcasts=True).all()
        
        # Create a task for scheduled broadcast
        if scheduled_time:
            # Ensure scheduled_time is timezone-aware
            if scheduled_time.tzinfo is None:
                # If no timezone info, assume it's in UTC
                scheduled_time = scheduled_time.replace(tzinfo=timezone.utc)
            
            delay = (scheduled_time - datetime.now(timezone.utc)).total_seconds()
            
            if delay > 0:
                # Schedule the broadcast as a background task
                logger.info(f"Scheduling broadcast for bot {bot_id} in {delay:.2f} seconds")
                # Pass bot_id instead of bot object to avoid session issues
                asyncio.create_task(self._delayed_broadcast(bot_id, text, parse_mode, delay))
                return
            # If scheduled time is in the past, send immediately
            logger.info(f"Scheduled time is in the past, sending immediately for bot {bot_id}")
            scheduled_time = None
        
        # Send immediately if no scheduled time or past time
        await self._send_broadcast_messages(bot, users, text, parse_mode)
    
    async def _delayed_broadcast(self, bot_id, text, parse_mode, delay):
        """Background task to send broadcast after delay"""
        logger.info(f"Starting delayed broadcast for bot {bot_id} after {delay:.2f} seconds")
        await asyncio.sleep(delay)
        
        # Create a new database session for the background task
        db = SessionLocal()
        try:
            # Get fresh data from database
            bot = TelegramBot.get_by_id(db, bot_id)
            if not bot:
                logger.error(f"Bot {bot_id} not found in delayed broadcast")
                return
                
            users = db.query(BotUser).filter_by(bot_id=bot_id, can_receive_broadcasts=True).all()
            await self._send_broadcast_messages(bot, users, text, parse_mode)
            logger.info(f"Completed delayed broadcast for bot {bot_id}")
        except Exception as e:
            logger.error(f"Error in delayed broadcast for bot {bot_id}: {e}")
        finally:
            db.close()
    
    async def _send_broadcast_messages(self, bot, users, text, parse_mode):
        """Send broadcast messages to all users"""
        logger.info(f"Sending broadcast to {len(users)} users for bot {bot.id}")
        queue = self.get_queue(bot.id)
        for bot_user in users:
            personalized_text = render_template(text, bot_user.user)
            await queue.put({
                "bot_token": bot.token,
                "chat_id": int(bot_user.telegram_user_id),
                "text": personalized_text,
                "parse_mode": parse_mode
            }) 