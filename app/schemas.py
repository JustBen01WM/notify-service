from typing import Literal
from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    phone: str | None = None


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: Literal["email", "sms"]
    subject: str | None = None
    body: str = Field(min_length=1)


class NotifyRequest(BaseModel):
    user_id: int
    type: Literal["email", "sms"]
    # Either write the content directly...
    content: str | None = Field(default=None, min_length=1, max_length=2000)
    subject: str | None = Field(default=None, max_length=255)
    # ...or use a saved template, e.g. {"template_name": "welcome", "variables": {"name": "Ada"}}
    template_name: str | None = None
    variables: dict[str, str] = {}


class SettingsUpdate(BaseModel):
    api_key: str | None = Field(default=None, max_length=300)  # "" clears the key
    from_email: str | None = Field(default=None, max_length=255)
    use_real: bool | None = None


class TestEmail(BaseModel):
    to: EmailStr
