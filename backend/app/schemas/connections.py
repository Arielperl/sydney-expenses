from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConnectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(default="קופת הדגמה", min_length=2, max_length=100)
    provider: Literal["demo-pay"] = "demo-pay"

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("יש להזין שם לחיבור")
        return value


class ConnectionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


class ConnectionResponse(BaseModel):
    id: str
    provider: str
    name: str
    enabled: bool
    webhook_path: str
    last_event_at: datetime | None
    created_at: datetime


class ConnectionSecretResponse(ConnectionResponse):
    signing_secret: str
