import hashlib
import hmac
import time
from typing import Dict, Optional

from app.core.config import settings


def check_telegram_auth(auth_data: Dict[str, str]) -> bool:
    """
    Validate Telegram authentication data

    For explanation see: https://core.telegram.org/widgets/login#checking-authorization
    """
    # Check if the auth data is fresh (no older than 1 day)
    if int(time.time()) - int(auth_data.get("auth_date", "0")) > 86400:
        return False

    # Create a data check string
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(auth_data.items()) if k != "hash"
    )

    # Compute the secret key
    secret_key = hashlib.sha256(settings.TELEGRAM_BOT_TOKEN.encode()).digest()

    # Calculate the hash
    computed_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()

    print(computed_hash)

    # Compare the computed hash with the received hash
    return computed_hash == auth_data.get("hash", "")


def extract_user_data(auth_data: Dict[str, str]) -> Optional[Dict[str, str]]:
    """Extract user data from Telegram login widget data"""
    if not check_telegram_auth(auth_data):
        print("Invalid Telegram authentication data")
        return None

    return {
        "telegram_id": str(auth_data.get("id", "")),
        "first_name": auth_data.get("first_name", ""),
        "last_name": auth_data.get("last_name", ""),
        "telegram_username": auth_data.get("username", ""),
        "photo_url": auth_data.get("photo_url", ""),
        "auth_date": auth_data.get("auth_date", "")
    }
