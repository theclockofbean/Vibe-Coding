"""Application configuration loaded from the project root .env file.

Secrets are represented by ``SecretStr`` and must never be printed directly.
This module only loads and validates configuration; it does not create database
connections or external service clients.
"""

from functools import lru_cache
from typing import Final, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]  # 指向 backend
load_dotenv(BASE_DIR / ".env")

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
ENV_FILE: Final[Path] = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Validated application settings."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(
        default="AI Knowledge Agent Platform",
        min_length=1,
        validation_alias="APP_NAME",
    )

    app_version: str = Field(
        default="0.1.0",
        min_length=1,
        validation_alias="APP_VERSION",
    )

    app_env: Literal["development", "test", "production"] = Field(
        default="development",
        validation_alias="APP_ENV",
    )

    app_debug: bool = Field(
        default=False,
        validation_alias="APP_DEBUG",
    )

    app_secret_key: SecretStr = Field(
        validation_alias="APP_SECRET_KEY",
    )

    database_host: str = Field(
        default="127.0.0.1",
        min_length=1,
        validation_alias="DATABASE_HOST",
    )

    database_port: int = Field(
        default=5432,
        ge=1,
        le=65535,
        validation_alias="DATABASE_PORT",
    )

    database_name: str = Field(
        min_length=1,
        validation_alias="DATABASE_NAME",
    )

    database_user: str = Field(
        min_length=1,
        validation_alias="DATABASE_USER",
    )

    database_password: SecretStr = Field(
        validation_alias="DATABASE_PASSWORD",
    )

    database_client_encoding: str = Field(
        default="UTF8",
        min_length=1,
        validation_alias="DATABASE_CLIENT_ENCODING",
    )

    database_sslmode: Literal[
        "disable",
        "allow",
        "prefer",
        "require",
        "verify-ca",
        "verify-full",
    ] = Field(
        default="prefer",
        validation_alias="DATABASE_SSLMODE",
    )

    database_connect_timeout_seconds: int = Field(
        default=5,
        ge=1,
        le=60,
        validation_alias="DATABASE_CONNECT_TIMEOUT_SECONDS",
    )

    @field_validator(
        "app_secret_key",
        "database_password",
    )
    @classmethod
    def validate_secret_not_blank(cls, value: SecretStr) -> SecretStr:
        """Reject empty or whitespace-only secret values."""

        if not value.get_secret_value().strip():
            raise ValueError("secret value must not be empty")

        return value

    @property
    def is_production(self) -> bool:
        """Return whether the application is running in production."""

        return self.app_env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return one cached settings instance for the current process."""

    return Settings()  # type: ignore[call-arg]


__all__ = [
    "ENV_FILE",
    "PROJECT_ROOT",
    "Settings",
    "get_settings",
]
