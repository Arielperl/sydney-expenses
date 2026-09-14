from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.business import BusinessOwned


class CardcomCredential(BusinessOwned, Base):
    """The Cardcom terminal credentials for exactly one `IntegrationConnection`
    (`provider="cardcom"`) — kept in a separate table from
    `integration_connections` specifically so that table (shared with Grow
    and demo-pay) never gains a sensitive, provider-specific column.

    `terminal_number` is Cardcom's merchant/terminal identifier — not secret
    on its own, but still business-specific, so it lives here rather than on
    the shared connection row. `encrypted_credentials` holds the owner's own
    real Cardcom `ApiName` (and optional `ApiPassword`) as a Fernet-encrypted
    JSON blob — see app/services/credential_encryption.py. The plaintext is
    recoverable only by the backend process holding
    `CARDCOM_CREDENTIAL_ENCRYPTION_KEY`, and is used only to call Cardcom's
    own server-to-server verification API
    (`POST /api/v11/LowProfile/GetLpResult`) — it is never returned by any
    API response, never logged, and never sent to the frontend.
    """

    __tablename__ = "cardcom_credentials"

    connection_id: Mapped[str] = mapped_column(
        ForeignKey("integration_connections.id", ondelete="CASCADE"), primary_key=True
    )
    terminal_number: Mapped[str] = mapped_column(String(40), nullable=False)
    encrypted_credentials: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
