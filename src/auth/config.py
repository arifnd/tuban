import logging
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config import settings

logger = logging.getLogger(__name__)

DEFAULT_SESSION_SECRET = "change-me-in-production-change-me-in-production"
MIN_SESSION_SECRET_LENGTH = 32
MIN_SESSION_SECRET_UNIQUE_CHARS = 8
LOCAL_ENVIRONMENTS = ("local", "test")
SECRET_GENERATION_HINT = 'Generate one with: python -c "import secrets;print(secrets.token_urlsafe(64))"'


class AuthConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AUTH_", env_file=".env", extra="ignore")

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/callback"

    SESSION_SECRET: str = DEFAULT_SESSION_SECRET
    SESSION_EXP_MINUTES: int = 480
    SECURE_COOKIES: bool = False

    DEV_LOGIN_ENABLED: bool = False

    def model_post_init(self, __context: object) -> None:
        env = settings.ENVIRONMENT
        self.SESSION_SECRET = self.SESSION_SECRET.strip()
        if env != "test":
            self._validate_session_secret()
        if env not in LOCAL_ENVIRONMENTS:
            self.SECURE_COOKIES = True
        if env not in LOCAL_ENVIRONMENTS and self.DEV_LOGIN_ENABLED:
            logger.warning("AUTH_DEV_LOGIN_ENABLED is set but ignored outside local/test environments; forcing it off.")
            self.DEV_LOGIN_ENABLED = False

    def _validate_session_secret(self) -> None:
        secret = self.SESSION_SECRET
        if not secret or secret == DEFAULT_SESSION_SECRET or secret.startswith("change-me"):
            raise RuntimeError(f"AUTH_SESSION_SECRET must be set to a strong value. {SECRET_GENERATION_HINT}")
        if len(secret) < MIN_SESSION_SECRET_LENGTH:
            raise RuntimeError(f"AUTH_SESSION_SECRET must be at least {MIN_SESSION_SECRET_LENGTH} characters. {SECRET_GENERATION_HINT}")
        if len(set(secret)) < MIN_SESSION_SECRET_UNIQUE_CHARS:
            raise RuntimeError(f"AUTH_SESSION_SECRET is too repetitive. {SECRET_GENERATION_HINT}")

    @property
    def dev_login_enabled(self) -> bool:
        return settings.is_local and self.DEV_LOGIN_ENABLED is True


@lru_cache
def get_auth_settings() -> AuthConfig:
    return AuthConfig()
