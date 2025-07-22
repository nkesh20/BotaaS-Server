from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship, Session
from app.models.base import Base

class ChatUserMessageCount(Base):
    __tablename__ = "chat_user_message_counts"
    __table_args__ = (
        UniqueConstraint("chat_id", "user_id", name="uq_chat_user"),
    )

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("telegram_chats.telegram_id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.telegram_id"), nullable=False, index=True)
    message_count = Column(Integer, default=0, nullable=False)

    user = relationship("User")
    chat = relationship("TelegramChat")

    @classmethod
    def get_by_id(cls, db: Session, chat_id: int, user_id: int):
        return db.query(cls).filter(cls.chat_id == chat_id, cls.user_id == user_id).first()

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
    def update(cls, db: Session, chat_id: int, user_id: int, update_data: dict):
        db_obj = cls.get_by_id(db, chat_id, user_id)
        if not db_obj:
            return None
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    @classmethod
    def delete(cls, db: Session, chat_id: int, user_id: int):
        db_obj = cls.get_by_id(db, chat_id, user_id)
        if not db_obj:
            return False
        db.delete(db_obj)
        db.commit()
        return True 