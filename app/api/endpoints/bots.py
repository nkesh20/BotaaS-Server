from datetime import datetime

import httpx
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.flow import Flow
from app.models.telegram_bot import TelegramBot
from app.models.user import User
from app.schemas.flow import FlowExecutionContext
from app.schemas.telegram_bot import (
    TelegramBotCreate,
    TelegramBotResponse,
    TelegramBotUpdate,
    TelegramBotListResponse
)
from app.services.flow_engine import FlowEngine
from app.services.telegram_service import TelegramService

logger = logging.getLogger(__name__)

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

        webhook_result = await TelegramService.setup_bot_automatically(
            bot_create.token,
            db_bot.id
        )

        if webhook_result["success"]:
            print(f"✅ Webhook automatically configured for bot {db_bot.username}")
        else:
            print(f"⚠️ Webhook setup failed for bot {db_bot.username}: {webhook_result.get('error')}")
            # Don't fail bot creation, just log the issue

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
async def update_bot(
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
    
    # Update bot information on Telegram if relevant fields are being updated
    telegram_api_base = f"https://api.telegram.org/bot{bot.token}"
    
    try:
        async with httpx.AsyncClient() as client:
            # Update bot name if provided
            if 'first_name' in update_data and update_data['first_name']:
                response = await client.post(
                    f"{telegram_api_base}/setMyName",
                    json={"name": update_data['first_name']}
                )
                if response.status_code != 200:
                    logger.warning(f"Failed to update bot name on Telegram: {response.text}")
            
            # Update bot description if provided
            if 'description' in update_data:
                response = await client.post(
                    f"{telegram_api_base}/setMyDescription",
                    json={"description": update_data['description'] or ""}
                )
                if response.status_code != 200:
                    logger.warning(f"Failed to update bot description on Telegram: {response.text}")
            
            # Update bot short description if provided
            if 'short_description' in update_data:
                response = await client.post(
                    f"{telegram_api_base}/setMyShortDescription",
                    json={"short_description": update_data['short_description'] or ""}
                )
                if response.status_code != 200:
                    logger.warning(f"Failed to update bot short description on Telegram: {response.text}")
                
    except Exception as e:
        # Log the error but don't fail the update - Telegram API might have issues
        logger.error(f"Error updating bot info on Telegram: {str(e)}")
    
    # Update in our database
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


@router.post("/{bot_id}/setup-webhook")
async def setup_bot_webhook(
        bot_id: int,
        webhook_base_url: str,  # e.g., "https://yourdomain.com"
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Set up webhook for a Telegram bot to start receiving messages.
    """
    try:
        # Get the bot
        bot = TelegramBot.get_by_id(db, bot_id)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")

        # Construct webhook URL
        webhook_url = f"{webhook_base_url}/api/v1/telegram/webhook/{bot.token}"

        # Set the webhook with Telegram
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.telegram.org/bot{bot.token}/setWebhook",
                json={"url": webhook_url}
            )
            result = response.json()

        if result.get("ok"):
            return {
                "success": True,
                "message": "Webhook configured successfully",
                "webhook_url": webhook_url,
                "bot_username": bot.username
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to set webhook: {result.get('description')}"
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{bot_id}/webhook-info")
async def get_webhook_info(
        bot_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Get current webhook information for a bot.
    """
    try:
        bot = TelegramBot.get_by_id(db, bot_id)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")

        # Get webhook info from Telegram
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.telegram.org/bot{bot.token}/getWebhookInfo"
            )
            webhook_info = response.json()

        # Get default flow info
        default_flow = Flow.get_default_flow(db, bot_id)

        return {
            "bot": {
                "id": bot.id,
                "username": bot.username,
                "first_name": bot.first_name
            },
            "webhook": webhook_info.get("result", {}),
            "default_flow": {
                "id": default_flow.id,
                "name": default_flow.name,
                "is_active": default_flow.is_active
            } if default_flow else None,
            "flows_count": len(Flow.get_by_bot_id(db, bot_id))
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))





@router.get("/{bot_id}/status", response_model=Dict[str, Any])
async def get_bot_status(
        bot_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive bot status including webhook verification.
    """
    try:
        # Get bot from database
        bot = TelegramBot.get_by_id(db, bot_id)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")

        # Verify webhook status
        webhook_status = await TelegramService.verify_webhook_setup(bot.token)

        # Get default flow info
        default_flow = Flow.get_default_flow(db, bot_id)
        all_flows = Flow.get_by_bot_id(db, bot_id)
        return {
            "bot": {
                "id": bot.id,
                "username": bot.username,
                "first_name": bot.first_name,
                "is_active": bot.is_active
            },
            "webhook": {
                "is_configured": webhook_status["is_configured"],
                "is_correct": webhook_status["is_correct"],
                "url": webhook_status.get("current_url"),
                "expected_url": webhook_status.get("expected_url")
            },
            "flows": {
                "default_flow": {
                    "id": default_flow.id,
                    "name": default_flow.name,
                    "is_active": default_flow.is_active
                } if default_flow else None,
                "total_count": len(all_flows),
                "active_count": len([f for f in all_flows if f.is_active])
            },
            "status": "ready" if (webhook_status["is_configured"] and default_flow) else "needs_setup"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{bot_id}/analytics", response_model=Dict[str, Any])
async def get_bot_analytics(
        bot_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Get analytics data for a specific bot including chat count.
    """
    try:
        # Get bot from database
        bot = TelegramBot.get_by_id(db, bot_id)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")

        # Count unique chats for this bot
        # We need to join through BotUser and ChatUserMessageCount to get unique chats
        from sqlalchemy import distinct, func
        from app.models.bot_user import BotUser
        from app.models.chat_user_message_count import ChatUserMessageCount

        # Get unique chat count for this bot
        chat_count_result = db.query(
            func.count(distinct(ChatUserMessageCount.chat_id))
        ).join(
            BotUser, BotUser.user_id == ChatUserMessageCount.user_id
        ).filter(
            BotUser.bot_id == bot_id
        ).scalar()

        # Get total message count for this bot
        message_count_result = db.query(
            func.sum(ChatUserMessageCount.message_count)
        ).join(
            BotUser, BotUser.user_id == ChatUserMessageCount.user_id
        ).filter(
            BotUser.bot_id == bot_id
        ).scalar()

        # Get unique user count for this bot
        user_count_result = db.query(
            func.count(distinct(BotUser.user_id))
        ).filter(
            BotUser.bot_id == bot_id
        ).scalar()

        # Get banned user count for this bot
        from app.models.banned_user import BannedUser
        banned_users_count = BannedUser.get_ban_count_for_bot(db, bot_id)

        return {
            "bot": {
                "id": bot.id,
                "username": bot.username,
                "first_name": bot.first_name
            },
            "analytics": {
                "total_chats": chat_count_result or 0,
                "total_messages": message_count_result or 0,
                "unique_users": user_count_result or 0,
                "banned_users": banned_users_count
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{bot_id}/fix-webhook")
async def fix_webhook(
        bot_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Automatically fix webhook configuration if it's broken.
    """
    try:
        bot = TelegramBot.get_by_id(db, bot_id)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")

        # Re-setup webhook
        result = await TelegramService.setup_bot_automatically(bot.token, bot.id)

        if result["success"]:
            return {
                "success": True,
                "message": "Webhook fixed successfully!",
                "webhook_url": result["webhook_url"]
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))