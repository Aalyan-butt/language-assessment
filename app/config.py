from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    frontend_origin: str = "http://localhost:5500"
    app_secret: str = Field(default="development-only-change-this-secret", min_length=24)
    google_client_id: str = ""
    google_client_secret: str = ""
    google_refresh_token: str = ""
    google_spreadsheet_id: str = ""
    google_drive_folder_id: str = ""
    session_idle_minutes: int = Field(default=120, ge=15, le=1440)
    account_lock_minutes: int = Field(default=2, ge=1, le=1440)
    max_login_failures: int = Field(default=5, ge=3, le=20)

    @field_validator("frontend_origin")
    @classmethod
    def clean_origin(cls, value: str) -> str:
        return value.rstrip("/")

    @property
    def google_ready(self) -> bool:
        return all((
            self.google_client_id,
            self.google_client_secret,
            self.google_refresh_token,
            self.google_spreadsheet_id,
        ))


@lru_cache
def get_settings() -> Settings:
    return Settings()
