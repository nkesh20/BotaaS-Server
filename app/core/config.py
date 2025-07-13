import os
from typing import List, Union
from pydantic import AnyHttpUrl, validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    API_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "BotaaS"
    DEBUG: bool = True

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:4200"]

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Database postgres
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost/botaas"
    WEBHOOK_BASE_URL: str = "https://81970232fc66.ngrok-free.app"

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "development_secret_key")
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "development_bot_token")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"

    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()