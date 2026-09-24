import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from src.users.models import UserRole


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: str
    avatar: str | None = None
    role: UserRole
    is_active: bool
    last_login: datetime | None = None


class UserRoleUpdate(BaseModel):
    role: UserRole


class UserActiveUpdate(BaseModel):
    is_active: bool


class ProfileUpdate(BaseModel):
    name: str
