from pydantic import BaseModel, validator, field_validator
from typing import Optional
from datetime import datetime


class TelegramBotBase(BaseModel):
    username: str
    first_name: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    bot_picture_url: Optional[str] = None
    description_picture_url: Optional[str] = None
    is_active: bool = True
    can_join_groups: bool = True
    can_read_all_group_messages: bool = False
    supports_inline_queries: bool = False


class TelegramBotCreate(BaseModel):
    token: str

    @field_validator('token')
    def validate_token(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Token cannot be empty')
        # Basic token format validation (should start with bot ID and contain colon)
        if ':' not in v:
            raise ValueError('Invalid token format')
        return v.strip()


class TelegramBotUpdate(BaseModel):
    first_name: Optional[str] = None
    description: Optional[str] = None
    short_description: Optional[str] = None
    bot_picture_url: Optional[str] = None
    description_picture_url: Optional[str] = None
    is_active: Optional[bool] = None
    can_join_groups: Optional[bool] = None
    can_read_all_group_messages: Optional[bool] = None
    supports_inline_queries: Optional[bool] = None


class TelegramBotResponse(TelegramBotBase):
    id: int
    user_id: int
    bot_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TelegramBotListResponse(BaseModel):
    bots: list[TelegramBotResponse]
    total: int
    skip: int
    limit: int
