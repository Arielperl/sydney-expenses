import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.business import BusinessOwned


class IntegrationConnection(BusinessOwned, Base):
    """A payment/POS webhook endpoint owned by exactly one business.

    Two distinct authentication models coexist here, one per provider:

    - `demo-pay` (HMAC-signed): the URL is stable (`/connections/{id}`) and
      the *secret* is what's rotated — derived from a server-side master key
      plus `secret_salt`, never stored in the database. Rotating the salt
      immediately invalidates the previous secret.
    - `grow` (no signing capability at all — see grow_provider.py): there is
      no secret to rotate, so the *URL itself* is the only credential. It's
      built from `url_token` (a separate random value from `id`, so rotating
      it swaps the URL without disturbing the connection's history, name, or
      activity log) rather than `id`, precisely so it can be rotated
      independently of the row's identity.
    """

    __tablename__ = "integration_connections"
    __table_args__ = (
        UniqueConstraint("business_id", "name", name="uq_integration_connections_business_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="demo-pay")
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    secret_salt: Mapped[str] = mapped_column(String(64), nullable=False)
    # Populated only for URL-is-the-credential providers (currently: grow).
    # Left null for demo-pay, which keeps using `id` in its webhook path.
    url_token: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
