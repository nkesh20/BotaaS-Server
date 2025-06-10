from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime
from sqlalchemy.orm import Session, relationship

from app.models.base import Base
from app.schemas.user import UserCreate, UserUpdate


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    telegram_id = Column(String, unique=True, index=True)
    telegram_username = Column(String, index=True)
    first_name = Column(String)
    last_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship with telegram bots
    telegram_bots = relationship("TelegramBot", back_populates="user", cascade="all, delete-orphan")

    @classmethod
    def get_by_id(cls, db: Session, user_id: int):
        return db.query(User).filter(User.id == user_id).first()

    @classmethod
    def get_by_telegram_id(cls, db: Session, telegram_id: str):
        return db.query(User).filter(User.telegram_id == telegram_id).first()

    @classmethod
    def get_by_username(cls, db: Session, username: str):
        return db.query(User).filter(User.username == username).first()

    @classmethod
    def get_users(cls, db: Session, skip: int = 0, limit: int = 100):
        return db.query(User).offset(skip).limit(limit).all()

    @classmethod
    def create(cls, db: Session, user: UserCreate):
        db_user = User(
            username=user.username,
            email=user.email,
            telegram_id=user.telegram_id,
            telegram_username=user.telegram_username,
            first_name=user.first_name,
            last_name=user.last_name,
            is_active=user.is_active
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

    @classmethod
    def update(cls, db: Session, user_id: int, user_update: UserUpdate):
        db_user = cls.get_by_id(db, user_id)
        if not db_user:
            return None

        update_data = user_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_user, field, value)

        db.commit()
        db.refresh(db_user)
        return db_user

    @classmethod
    def delete_user(cls, db: Session, user_id: int) -> bool:
        db_user = cls.get_by_id(db, user_id)
        if not db_user:
            return False

        db.delete(db_user)
        db.commit()
        return True
