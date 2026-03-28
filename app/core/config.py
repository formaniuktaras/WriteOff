from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "WriteOff"
    env: str = "production"
    debug: bool = False
    secret_key: str
    session_cookie_name: str = "writeoff_session"
    session_max_age: int = 60 * 60 * 8
    session_secure: bool = False
    session_samesite: str = "lax"

    database_url: str
    storage_root: str = "/data/storage"
    backups_root: str = "/data/backups"
    max_upload_mb: int = 25
    allowed_upload_extensions: str = ".docx,.docm,.xlsx,.xlsm,.pdf,.zip,.txt,.jpg,.jpeg,.png"

    @field_validator("session_samesite")
    @classmethod
    def validate_samesite(cls, value: str) -> str:
        supported = {"lax", "strict", "none"}
        normalized = value.lower()
        if normalized not in supported:
            raise ValueError(f"session_samesite must be one of {supported}")
        return normalized


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[arg-type]
