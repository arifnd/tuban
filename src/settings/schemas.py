from pydantic import BaseModel, Field, field_validator, model_validator

from src.settings.theme import DEFAULT_COLOR, PALETTES
from src.storage.constants import SAFE_EXTENSIONS


class SettingsUpdate(BaseModel):
    app_name: str = Field(min_length=1, max_length=100)
    default_language: str = Field(pattern=r"^(en|id)$")
    theme_color: str = Field(default=DEFAULT_COLOR)
    sla_urgent_hours: int = Field(ge=1, le=1000)
    sla_high_hours: int = Field(ge=1, le=1000)
    sla_normal_hours: int = Field(ge=1, le=1000)
    sla_low_hours: int = Field(ge=1, le=1000)
    ticket_number_prefix: str = Field(default="TKT", min_length=1, max_length=10)
    upload_max_size_mb: int = Field(ge=1, le=10240)
    allowed_extensions: list[str] = Field(min_length=1)
    open_registration: bool = False
    require_approval: bool = False
    contact_email: str = Field(default="", max_length=200)
    contact_phone: str = Field(default="", max_length=50)
    contact_address: str = Field(default="", max_length=300)
    landing_heading: str = Field(default="", max_length=200)
    landing_subheading: str = Field(default="", max_length=500)
    social_facebook: str = Field(default="", max_length=300)
    social_instagram: str = Field(default="", max_length=300)
    social_x: str = Field(default="", max_length=300)
    social_linkedin: str = Field(default="", max_length=300)
    social_youtube: str = Field(default="", max_length=300)
    smtp_enabled: bool = False
    smtp_host: str = Field(default="", max_length=255)
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str = Field(default="", max_length=200)
    smtp_password: str = Field(default="", max_length=500)
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    smtp_from_email: str = Field(default="", max_length=200)
    smtp_from_name: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def _validate_smtp_transport(self) -> "SettingsUpdate":
        if self.smtp_use_tls and self.smtp_use_ssl:
            raise ValueError("Enable either STARTTLS or SSL, not both")
        return self

    @field_validator("theme_color")
    @classmethod
    def _validate_theme_color(cls, value: str) -> str:
        if value not in PALETTES:
            raise ValueError("Unknown theme color")
        return value

    @field_validator("allowed_extensions")
    @classmethod
    def _validate_allowed_extensions(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in value:
            extension = str(item).strip().lower().lstrip(".")
            if not extension:
                continue
            if extension not in SAFE_EXTENSIONS:
                raise ValueError(f"Unsupported file type: {extension}")
            if extension not in normalized:
                normalized.append(extension)
        if not normalized:
            raise ValueError("At least one file type is required")
        return normalized

    @field_validator("ticket_number_prefix")
    @classmethod
    def _validate_ticket_number_prefix(cls, value: str) -> str:
        prefix = value.strip().strip("-").upper()
        if not prefix or not prefix.isalnum():
            raise ValueError("Ticket number prefix may only contain letters and numbers")
        return prefix

    @field_validator("contact_email")
    @classmethod
    def _validate_contact_email(cls, value: str) -> str:
        if value and "@" not in value:
            raise ValueError("Enter a valid contact email address")
        return value

    @field_validator("smtp_from_email")
    @classmethod
    def _validate_smtp_from_email(cls, value: str) -> str:
        if value and "@" not in value:
            raise ValueError("Enter a valid from email address")
        return value

    @field_validator("social_facebook", "social_instagram", "social_x", "social_linkedin", "social_youtube")
    @classmethod
    def _validate_social_url(cls, value: str) -> str:
        if value and not value.startswith(("http://", "https://")):
            raise ValueError("Social links must start with http:// or https://")
        return value
