from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# demo-pay: development/test only, blocked from creation in production (see
# app/api/routes/connections.py:_reject_demo_pay_in_production). grow and
# cardcom are both real, production-allowed providers with completely
# separate adapters, authentication, and configuration — see
# app/services/ingestion/grow_provider.py and cardcom_provider.py.
ConnectionProvider = Literal["demo-pay", "grow", "cardcom"]


class ConnectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(default="חיבור חדש", min_length=2, max_length=100)
    provider: ConnectionProvider = "grow"

    # Cardcom only — the business owner's own real Cardcom terminal
    # credentials, required only for this provider. Never displayed back
    # after creation (see ConnectionResponse) and stored only encrypted
    # (see app/models/cardcom_credential.py). Cardcom's own documentation
    # defines no separate "signing secret" concept at all — these ARE the
    # credentials, not an additional secret on top of them.
    cardcom_terminal_number: str | None = Field(default=None, max_length=40)
    cardcom_api_name: str | None = Field(default=None, max_length=100)
    cardcom_api_password: str | None = Field(default=None, max_length=200)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("יש להזין שם לחיבור")
        return value

    @model_validator(mode="after")
    def _validate_cardcom_fields(self) -> "ConnectionCreate":
        if self.provider == "cardcom":
            if not self.cardcom_terminal_number or not self.cardcom_terminal_number.strip():
                raise ValueError("יש להזין מספר מסוף Cardcom")
            if not self.cardcom_api_name or not self.cardcom_api_name.strip():
                raise ValueError("יש להזין שם משתמש API של Cardcom")
        return self


class ConnectionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


class ConnectionEventCounts(BaseModel):
    received: int = 0
    processed: int = 0
    duplicate: int = 0
    failed: int = 0
    rejected: int = 0


class ConnectionResponse(BaseModel):
    id: str
    provider: str
    name: str
    enabled: bool
    webhook_path: str
    # True only once a real event has actually been received for this
    # connection — the frontend must never claim "verified" before this is
    # true (see docs/security.md and the frontend Grow panel).
    has_received_event: bool
    last_event_at: datetime | None
    created_at: datetime
    event_counts: ConnectionEventCounts
    # Cardcom only — not sensitive, shown so the owner can confirm which
    # terminal a connection maps to. Always null for every other provider.
    cardcom_terminal_number: str | None = None


class ConnectionSecretResponse(ConnectionResponse):
    # Populated only for demo-pay (HMAC-signed). Always null for grow —
    # Grow has no signing capability, and this field must never be
    # requested from or displayed to a Grow-connecting business; see
    # app/api/routes/connections.py.
    signing_secret: str | None = None
