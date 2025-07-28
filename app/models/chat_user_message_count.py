from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint, BigInteger, Date, func
from sqlalchemy.orm import relationship, Session
from datetime import datetime, date
from app.models.base import Base

class ChatUserMessageCount(Base):
    __tablename__ = "chat_user_message_counts"
    __table_args__ = (
        UniqueConstraint("chat_id", "user_id", "date", name="uq_chat_user_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(BigInteger, ForeignKey("telegram_chats.telegram_id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True, default=date.today)
    message_count = Column(Integer, default=0, nullable=False)

    user = relationship("User")
    chat = relationship("TelegramChat")

    @classmethod
    def get_by_id(cls, db: Session, chat_id: int, user_id: int, message_date: date = None):
        """Get message count for a specific chat, user, and date."""
        if message_date is None:
            message_date = date.today()
        return db.query(cls).filter(
            cls.chat_id == chat_id, 
            cls.user_id == user_id,
            cls.date == message_date
        ).first()

    @classmethod
    def get_all(cls, db: Session, skip: int = 0, limit: int = 100):
        return db.query(cls).offset(skip).limit(limit).all()

    @classmethod
    def create(cls, db: Session, data: dict):
        db_obj = cls(**data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    @classmethod
    def update(cls, db: Session, chat_id: int, user_id: int, update_data: dict, message_date: date = None):
        if message_date is None:
            message_date = date.today()
        db_obj = cls.get_by_id(db, chat_id, user_id, message_date)
        if not db_obj:
            return None
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    @classmethod
    def delete(cls, db: Session, chat_id: int, user_id: int, message_date: date = None):
        if message_date is None:
            message_date = date.today()
        db_obj = cls.get_by_id(db, chat_id, user_id, message_date)
        if not db_obj:
            return False
        db.delete(db_obj)
        db.commit()
        return True

    @classmethod
    def increment_message_count(cls, db: Session, chat_id: int, user_id: int, message_date: date = None):
        """Increment message count for a specific date, creating record if it doesn't exist."""
        if message_date is None:
            message_date = date.today()
        
        db_obj = cls.get_by_id(db, chat_id, user_id, message_date)
        if db_obj:
            # Update existing record
            db_obj.message_count += 1
            db.commit()
            db.refresh(db_obj)
        else:
            # Create new record
            db_obj = cls(
                chat_id=chat_id,
                user_id=user_id,
                date=message_date,
                message_count=1
            )
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
        return db_obj

    @classmethod
    def get_total_messages_for_period(cls, db: Session, bot_id: int, start_date: date = None, end_date: date = None):
        """Get total messages for a bot within a date range."""
        from app.models.bot_user import BotUser
        
        query = db.query(cls).join(
            BotUser, cls.user_id == BotUser.user_id
        ).filter(BotUser.bot_id == bot_id)
        
        if start_date:
            query = query.filter(cls.date >= start_date)
        if end_date:
            query = query.filter(cls.date <= end_date)
        
        return query.with_entities(func.sum(cls.message_count)).scalar() or 0

    @classmethod
    def get_unique_chats_for_period(cls, db: Session, bot_id: int, start_date: date = None, end_date: date = None):
        """Get unique chat count for a bot within a date range."""
        from app.models.bot_user import BotUser
        
        query = db.query(func.count(func.distinct(cls.chat_id))).join(
            BotUser, cls.user_id == BotUser.user_id
        ).filter(BotUser.bot_id == bot_id)
        
        if start_date:
            query = query.filter(cls.date >= start_date)
        if end_date:
            query = query.filter(cls.date <= end_date)
        
        return query.scalar() or 0 