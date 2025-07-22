from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.base import Base

class TelegramChat(Base):
    __tablename__ = "telegram_chats"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True, nullable=False)
    type = Column(String, nullable=False)  # e.g., 'private', 'group', 'supergroup', 'channel'
    title = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    @classmethod
    def get_by_id(cls, db: Session, telegram_id: int):
        return db.query(cls).filter(cls.telegram_id == telegram_id).first()

    @classmethod
    def get_all(cls, db: Session, skip: int = 0, limit: int = 100):
        return db.query(cls).offset(skip).limit(limit).all()

    @classmethod
    def create(cls, db: Session, chat_data: dict):
        db_chat = cls(**chat_data)
        db.add(db_chat)
        db.commit()
        db.refresh(db_chat)
        return db_chat

    @classmethod
    def update(cls, db: Session, telegram_id: int, update_data: dict):
        db_chat = cls.get_by_id(db, telegram_id)
        if not db_chat:
            return None
        for field, value in update_data.items():
            if hasattr(db_chat, field):
                setattr(db_chat, field, value)
        db.commit()
        db.refresh(db_chat)
        return db_chat

    @classmethod
    def delete(cls, db: Session, telegram_id: int):
        db_chat = cls.get_by_id(db, telegram_id)
        if not db_chat:
            return False
        db.delete(db_chat)
        db.commit()
        return True 