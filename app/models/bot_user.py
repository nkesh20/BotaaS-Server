from sqlalchemy import Column, Integer, ForeignKey, DateTime, Boolean, String, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base

class BotUser(Base):
    __tablename__ = "bot_users"
    __table_args__ = (UniqueConstraint("bot_id", "user_id", name="uq_bot_user"),)

    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("telegram_bots.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    telegram_user_id = Column(String, index=True)
    first_interaction = Column(DateTime, default=datetime.utcnow)
    can_receive_broadcasts = Column(Boolean, default=True)

    user = relationship("User")
    bot = relationship("TelegramBot")

    @classmethod
    def get_or_create(cls, db, bot_id, user_id, telegram_user_id=None):
        instance = db.query(cls).filter_by(bot_id=bot_id, user_id=user_id).first()
        if instance:
            return instance, False
        instance = cls(
            bot_id=bot_id,
            user_id=user_id,
            telegram_user_id=telegram_user_id,
            can_receive_broadcasts=True
        )
        db.add(instance)
        db.commit()
        db.refresh(instance)
        return instance, True 