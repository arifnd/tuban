from pydantic import BaseModel, Field


class SettingsUpdate(BaseModel):
    app_name: str = Field(min_length=1, max_length=100)
    default_language: str = Field(pattern=r"^(en|id)$")
    sla_urgent_hours: int = Field(ge=1, le=1000)
    sla_high_hours: int = Field(ge=1, le=1000)
    sla_normal_hours: int = Field(ge=1, le=1000)
    sla_low_hours: int = Field(ge=1, le=1000)
    upload_max_size_mb: int = Field(ge=1, le=10240)
    allowed_extensions: list[str] = Field(min_length=1)
    open_registration: bool = False
    require_approval: bool = False
