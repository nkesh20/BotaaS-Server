import httpx
from typing import Dict, Optional
from fastapi import HTTPException


class TelegramService:
    BASE_URL = "https://api.telegram.org/bot"

    @classmethod
    async def get_bot_info(cls, token: str) -> Dict:
        """
        Fetch bot information from Telegram API using the bot token
        """
        url = f"{cls.BASE_URL}{token}/getMe"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10.0)

            if response.status_code != 200:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid bot token or Telegram API error"
                )

            data = response.json()

            if not data.get("ok"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Telegram API error: {data.get('description', 'Unknown error')}"
                )

            bot_info = data["result"]

            # Validate that this is actually a bot
            if not bot_info.get("is_bot"):
                raise HTTPException(
                    status_code=400,
                    detail="The provided token does not belong to a bot"
                )

            return {
                "id": bot_info["id"],
                "username": bot_info["username"],
                "first_name": bot_info["first_name"],
                "is_bot": bot_info["is_bot"],
                "can_join_groups": bot_info.get("can_join_groups", True),
                "can_read_all_group_messages": bot_info.get("can_read_all_group_messages", False),
                "supports_inline_queries": bot_info.get("supports_inline_queries", False),
                "token": token
            }

        except httpx.TimeoutException:
            raise HTTPException(
                status_code=408,
                detail="Timeout while connecting to Telegram API"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error connecting to Telegram API: {str(e)}"
            )

    @classmethod
    async def get_bot_description(cls, token: str) -> Dict[str, Optional[str]]:
        """
        Fetch bot description from Telegram API
        """
        url = f"{cls.BASE_URL}{token}/getMyDescription"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10.0)

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    result = data.get("result", {})
                    return {
                        "description": result.get("description"),
                    }

            return {"description": None}

        except (httpx.TimeoutException, httpx.RequestError):
            # If we can't get description, it's not critical
            return {"description": None}

    @classmethod
    async def get_bot_short_description(cls, token: str) -> Dict[str, Optional[str]]:
        """
        Fetch bot short description from Telegram API
        """
        url = f"{cls.BASE_URL}{token}/getMyShortDescription"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10.0)

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    result = data.get("result", {})
                    return {
                        "short_description": result.get("short_description"),
                    }

            return {"short_description": None}

        except (httpx.TimeoutException, httpx.RequestError):
            # If we can't get short description, it's not critical
            return {"short_description": None}

    @classmethod
    async def get_full_bot_info(cls, token: str) -> Dict:
        """
        Get complete bot information including descriptions
        """
        # Get basic bot info
        bot_info = await cls.get_bot_info(token)

        # Get descriptions (these are optional and won't fail the entire process)
        description_info = await cls.get_bot_description(token)
        short_description_info = await cls.get_bot_short_description(token)

        # Merge all information
        bot_info.update(description_info)
        bot_info.update(short_description_info)

        return bot_info
