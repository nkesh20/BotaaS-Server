from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.telegram_bot import TelegramBot
from app.models.user import User
from app.schemas.telegram_bot import (
    TelegramBotCreate,
    TelegramBotResponse,
    TelegramBotUpdate,
    TelegramBotListResponse
)
from app.services.telegram_service import TelegramService

router = APIRouter(prefix="/telegram-bots", tags=["telegram-bots"])


@router.post("/", response_model=TelegramBotResponse)
async def create_telegram_bot(
        bot_create: TelegramBotCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Create a new Telegram bot by providing its token.
    The bot details will be fetched from Telegram API.
    """
    # Check if bot with this token already exists
    existing_bot = TelegramBot.get_by_token(db, bot_create.token)
    if existing_bot:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bot with this token already exists"
        )

    try:
        # Get bot information from Telegram API
        bot_info = await TelegramService.get_full_bot_info(bot_create.token)

        # Check if bot with this bot_id already exists
        existing_bot_by_id = TelegramBot.get_by_bot_id(db, str(bot_info["id"]))
        if existing_bot_by_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This bot is already registered in the system"
            )

        # Create bot in database
        db_bot = TelegramBot.create(db, current_user.id, bot_info)

        return db_bot

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create bot: {str(e)}"
        )


@router.get("/", response_model=TelegramBotListResponse)
def get_user_bots(
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Get all Telegram bots for the current user
    """
    bots = TelegramBot.get_user_bots(db, current_user.id, skip, limit)
    total = len(TelegramBot.get_user_bots(db, current_user.id))

    return TelegramBotListResponse(
        bots=bots,
        total=total,
        skip=skip,
        limit=limit
    )


@router.get("/{bot_id}", response_model=TelegramBotResponse)
def get_bot(
        bot_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Get a specific Telegram bot by ID
    """
    bot = TelegramBot.get_by_id(db, bot_id)

    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )

    # Check if bot belongs to current user
    if bot.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this bot"
        )

    return bot


@router.put("/{bot_id}", response_model=TelegramBotResponse)
def update_bot(
        bot_id: int,
        bot_update: TelegramBotUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Update a Telegram bot
    """
    bot = TelegramBot.get_by_id(db, bot_id)

    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )

    # Check if bot belongs to current user
    if bot.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this bot"
        )

    update_data = bot_update.dict(exclude_unset=True)
    updated_bot = TelegramBot.update(db, bot_id, update_data)

    if not updated_bot:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update bot"
        )

    return updated_bot


@router.post("/{bot_id}/refresh", response_model=TelegramBotResponse)
async def refresh_bot_info(
        bot_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Refresh bot information from Telegram API
    """
    bot = TelegramBot.get_by_id(db, bot_id)

    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )

    # Check if bot belongs to current user
    if bot.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to refresh this bot"
        )

    try:
        # Get fresh bot information from Telegram API
        bot_info = await TelegramService.get_full_bot_info(bot.token)

        # Update bot with fresh information
        update_data = {
            "first_name": bot_info["first_name"],
            "username": bot_info["username"],
            "description": bot_info.get("description"),
            "short_description": bot_info.get("short_description"),
            "can_join_groups": bot_info.get("can_join_groups", True),
            "can_read_all_group_messages": bot_info.get("can_read_all_group_messages", False),
            "supports_inline_queries": bot_info.get("supports_inline_queries", False),
        }

        updated_bot = TelegramBot.update(db, bot_id, update_data)
        return updated_bot

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh bot info: {str(e)}"
        )


@router.post("/{bot_id}/toggle", response_model=TelegramBotResponse)
def toggle_bot_active(
        bot_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Toggle bot active status
    """
    bot = TelegramBot.get_by_id(db, bot_id)

    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )

    # Check if bot belongs to current user
    if bot.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this bot"
        )

    updated_bot = TelegramBot.toggle_active(db, bot_id)

    if not updated_bot:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to toggle bot status"
        )

    return updated_bot


@router.delete("/{bot_id}")
def delete_bot(
        bot_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Delete a Telegram bot
    """
    bot = TelegramBot.get_by_id(db, bot_id)

    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )

    # Check if bot belongs to current user
    if bot.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this bot"
        )

    success = TelegramBot.delete(db, bot_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete bot"
        )

    return {"message": "Bot deleted successfully"}
