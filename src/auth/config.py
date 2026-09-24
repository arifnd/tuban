from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config import settings


class AuthConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AUTH_", env_file=".env", extra="ignore")

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/callback"

    SESSION_SECRET: str = "change-me-in-production-change-me-in-production"
    SESSION_EXP_MINUTES: int = 480
    SECURE_COOKIES: bool = False

    DEV_LOGIN_ENABLED: bool | None = None

    def model_post_init(self, __context: object) -> None:
        env = settings.ENVIRONMENT
        if env not in ("local", "test") and (not self.SESSION_SECRET or self.SESSION_SECRET.startswith("change-me")):
            raise RuntimeError(
                "SESSION_SECRET must be set to a strong value in staging/production. "
                'Generate one with: python -c "import secrets;print(secrets.token_urlsafe(64))"'
            )
        if env not in ("local", "test") and self.dev_login_enabled:
            raise RuntimeError("Dev login (AUTH_DEV_LOGIN_ENABLED) must not be enabled outside local/test environments.")
        if env == "production":
            self.SECURE_COOKIES = True

    @property
    def dev_login_enabled(self) -> bool:
        if self.DEV_LOGIN_ENABLED is not None:
            return self.DEV_LOGIN_ENABLED
        return settings.ENVIRONMENT == "local"


auth_settings = AuthConfig()
