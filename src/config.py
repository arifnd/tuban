from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        extra="ignore",
    )

    APP_NAME: str = "Tuban Helpdesk"
    ENVIRONMENT: str = "local"

    DATABASE_URL: str = "sqlite+aiosqlite:///./instance/tuban.db"

    INITIAL_ADMIN_EMAIL: str = ""

    @field_validator("DATABASE_URL")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return "postgresql+asyncpg://" + value[len("postgres://") :]
        if value.startswith("postgresql://"):
            return "postgresql+asyncpg://" + value[len("postgresql://") :]
        if value.startswith("sqlite"):
            sep = ":///"
            if sep in value:
                path = value.split(sep, 1)[1]
                if not path.startswith("/"):
                    resolved = PROJECT_ROOT / path
                    return f"{value.split(sep, 1)[0]}{sep}{resolved}"
        return value

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def sqlite_path(self) -> Path | None:
        if not self.is_sqlite:
            return None
        sep = ":///"
        if sep not in self.DATABASE_URL:
            return None
        return Path(self.DATABASE_URL.split(sep, 1)[1])


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
