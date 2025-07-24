import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.bot_user import BotUser
from app.models.telegram_bot import TelegramBot
from app.services.telegram_service import TelegramService

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
        delay = (scheduled_time - datetime.now(timezone.utc)).total_seconds() if scheduled_time else 0
        if delay > 0:
            await asyncio.sleep(delay)
        queue = self.get_queue(bot_id)
        for bot_user in users:
            personalized_text = render_template(text, bot_user.user)
            await queue.put({
                "bot_token": bot.token,
                "chat_id": int(bot_user.telegram_user_id),
                "text": personalized_text,
                "parse_mode": parse_mode
            }) 