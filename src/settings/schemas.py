from pydantic import BaseModel, Field, field_validator

from src.settings.theme import PALETTES


class SettingsUpdate(BaseModel):
    app_name: str = Field(min_length=1, max_length=100)
    default_language: str = Field(pattern=r"^(en|id)$")
    theme_color: str = Field(default="green")
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
    social_facebook: str = Field(default="", max_length=300)
    social_instagram: str = Field(default="", max_length=300)
    social_x: str = Field(default="", max_length=300)
    social_linkedin: str = Field(default="", max_length=300)
    social_youtube: str = Field(default="", max_length=300)

    @field_validator("theme_color")
    @classmethod
    def _validate_theme_color(cls, value: str) -> str:
        if value not in PALETTES:
            raise ValueError("Unknown theme color")
        return value

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

    @field_validator("social_facebook", "social_instagram", "social_x", "social_linkedin", "social_youtube")
    @classmethod
    def _validate_social_url(cls, value: str) -> str:
        if value and not value.startswith(("http://", "https://")):
            raise ValueError("Social links must start with http:// or https://")
        return value
