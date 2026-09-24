from pydantic import BaseModel, EmailStr


class DevLoginIn(BaseModel):
    email: EmailStr
