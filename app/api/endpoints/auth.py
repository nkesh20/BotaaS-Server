from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.api.deps import get_current_user
from app.core.security import create_access_token
from app.core.telegram_auth import extract_user_data
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserSchema, UserCreate

router = APIRouter()


@router.post("/telegram-login/", response_model=Dict[str, str])
async def telegram_login(auth_data: Dict[str, Any], db: Session = Depends(get_db)):
    """
    Authenticate user with Telegram login data
    """
    user_data = extract_user_data(auth_data)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram authentication data"
        )

    # Check if user exists
    db_user = User.get_by_telegram_id(db, user_data["telegram_id"])

    # If user doesn't exist, create a new one
    if not db_user:
        print(user_data)
        user_create = UserCreate(
            username=user_data["telegram_username"] or f"user_{user_data['telegram_id']}",
            telegram_id=user_data["telegram_id"],
            telegram_username=user_data["telegram_username"],
            first_name=user_data["first_name"],
            last_name=user_data["last_name"],
        )
        db_user = User.create(db, user_create)

    # Generate access token
    access_token = create_access_token(
        subject=str(db_user.id), telegram_id=db_user.telegram_id
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me/", response_model=UserSchema)
async def read_users_me(
        current_user: UserSchema = Depends(get_current_user)
):
    """
    Get current user information
    """
    return current_user
