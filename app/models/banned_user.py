from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, BigInteger
from sqlalchemy.orm import relationship, Session
from datetime import datetime
from app.models.base import Base

class BannedUser(Base):
    __tablename__ = "banned_users"

    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("telegram_bots.id"), nullable=False, index=True)
    telegram_user_id = Column(BigInteger, nullable=False, index=True)
    chat_id = Column(BigInteger, nullable=False, index=True)
    banned_at = Column(DateTime, default=datetime.utcnow)
    unbanned_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)  # True if currently banned, False if unbanned
    reason = Column(String, nullable=True)
    
    # Relationships
    bot = relationship("TelegramBot")

    @classmethod
    def get_by_id(cls, db: Session, banned_user_id: int):
        return db.query(cls).filter(cls.id == banned_user_id).first()

    @classmethod
    def get_active_bans_for_bot(cls, db: Session, bot_id: int):
        """Get all active bans for a specific bot."""
        return db.query(cls).filter(
            cls.bot_id == bot_id,
            cls.is_active == True
        ).all()

    @classmethod
    def get_ban_count_for_bot(cls, db: Session, bot_id: int):
        """Get the count of currently banned users for a bot."""
        return db.query(cls).filter(
            cls.bot_id == bot_id,
            cls.is_active == True
        ).count()

    @classmethod
    def get_total_ban_count_for_bot(cls, db: Session, bot_id: int):
        """Get the total count of bans (including unbanned) for a bot."""
        return db.query(cls).filter(cls.bot_id == bot_id).count()

    @classmethod
    def create_ban(cls, db: Session, bot_id: int, telegram_user_id: int, chat_id: int, reason: str = None):
        """Create a new ban record."""
        db_ban = cls(
            bot_id=bot_id,
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            reason=reason
        )
        db.add(db_ban)
        db.commit()
        db.refresh(db_ban)
        return db_ban

    @classmethod
    def unban_user(cls, db: Session, bot_id: int, telegram_user_id: int, chat_id: int):
        """Mark a user as unbanned."""
        db_ban = db.query(cls).filter(
            cls.bot_id == bot_id,
            cls.telegram_user_id == telegram_user_id,
            cls.chat_id == chat_id,
            cls.is_active == True
        ).first()
        
        if db_ban:
            db_ban.is_active = False
            db_ban.unbanned_at = datetime.utcnow()
            db.commit()
            db.refresh(db_ban)
            return db_ban
        return None

    @classmethod
    def get_all(cls, db: Session, skip: int = 0, limit: int = 100):
        return db.query(cls).offset(skip).limit(limit).all() 