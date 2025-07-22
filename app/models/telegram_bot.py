from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import Session, relationship
from datetime import datetime
from typing import Optional

from app.models.base import Base


class TelegramBot(Base):
    __tablename__ = "telegram_bots"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Bot details from Telegram API
    bot_id = Column(String, unique=True, index=True, nullable=False)  # Telegram bot ID
    username = Column(String, unique=True, index=True, nullable=False)  # Bot username
    first_name = Column(String, nullable=False)  # Bot display name
    token = Column(String, nullable=False)

    # Editable bot details
    description = Column(Text, nullable=True)
    short_description = Column(Text, nullable=True)
    about = Column(Text, nullable=True)  # Bot about text
    bot_picture_url = Column(String, nullable=True)  # Bot profile picture URL
    description_picture_url = Column(String, nullable=True)  # Description picture URL

    # Bot settings
    is_active = Column(Boolean, default=True)
    can_join_groups = Column(Boolean, default=True)
    can_read_all_group_messages = Column(Boolean, default=False)
    supports_inline_queries = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    user = relationship("User", back_populates="telegram_bots")
    flows = relationship("Flow", back_populates="bot", cascade="all, delete-orphan")


    @classmethod
    def get_by_id(cls, db: Session, bot_id: int):
        return db.query(cls).filter(cls.id == bot_id).first()

    @classmethod
    def get_by_bot_id(cls, db: Session, bot_id: str):
        return db.query(cls).filter(cls.bot_id == bot_id).first()

    @classmethod
    def get_by_username(cls, db: Session, username: str):
        return db.query(cls).filter(cls.username == username).first()

    @classmethod
    def get_by_token(cls, db: Session, token: str):
        return db.query(cls).filter(cls.token == token).first()

    @classmethod
    def get_user_bots(cls, db: Session, user_id: int, skip: int = 0, limit: int = 100):
        return db.query(cls).filter(cls.user_id == user_id).offset(skip).limit(limit).all()

    @classmethod
    def create(cls, db: Session, user_id: int, bot_data: dict):
        db_bot = cls(
            user_id=user_id,
            bot_id=str(bot_data["id"]),
            username=bot_data["username"],
            first_name=bot_data["first_name"],
            token=bot_data["token"],
            description=bot_data.get("description"),
            short_description=bot_data.get("short_description"),
            can_join_groups=bot_data.get("can_join_groups", True),
            can_read_all_group_messages=bot_data.get("can_read_all_group_messages", False),
            supports_inline_queries=bot_data.get("supports_inline_queries", False),
        )
        db.add(db_bot)
        db.commit()
        db.refresh(db_bot)
        return db_bot

    @classmethod
    def update(cls, db: Session, bot_id: int, update_data: dict):
        db_bot = cls.get_by_id(db, bot_id)
        if not db_bot:
            return None

        for field, value in update_data.items():
            if hasattr(db_bot, field):
                setattr(db_bot, field, value)

        db_bot.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_bot)
        return db_bot

    @classmethod
    def delete(cls, db: Session, bot_id: int) -> bool:
        db_bot = cls.get_by_id(db, bot_id)
        if not db_bot:
            return False

        db.delete(db_bot)
        db.commit()
        return True

    @classmethod
    def toggle_active(cls, db: Session, bot_id: int) -> Optional["TelegramBot"]:
        db_bot = cls.get_by_id(db, bot_id)
        if not db_bot:
            return None

        db_bot.is_active = not db_bot.is_active
        db_bot.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_bot)
        return db_bot
