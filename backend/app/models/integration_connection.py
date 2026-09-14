import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.business import BusinessOwned


class IntegrationConnection(BusinessOwned, Base):
    """A payment/POS webhook endpoint owned by exactly one business.

    The signing secret is derived from a server-side master key and the
    per-connection salt. It is intentionally never stored in the database.
    Rotating the salt immediately invalidates the previous secret.
    """

    __tablename__ = "integration_connections"
    __table_args__ = (
        UniqueConstraint("business_id", "name", name="uq_integration_connections_business_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="demo-pay")
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    secret_salt: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
