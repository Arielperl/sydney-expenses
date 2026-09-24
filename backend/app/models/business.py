import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Numeric, ForeignKey, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

LEGACY_BUSINESS_ID = "00000000-0000-4000-8000-000000000001"

class Business(Base):
    __tablename__ = "businesses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100))
    country_code: Mapped[str] = mapped_column(String(2), default="IL")
    currency: Mapped[str] = mapped_column(String(3), default="ILS")
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Jerusalem")
    vat_rate: Mapped[float] = mapped_column(Numeric(6,4), default=0.18)
    business_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class BusinessMember(Base):
    __tablename__ = "business_members"
    __table_args__ = (CheckConstraint("role in ('owner','manager','viewer')", name="ck_member_role"),)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), primary_key=True, unique=True)
    role: Mapped[str] = mapped_column(String(16), default="owner")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AppAccount(Base):
    """Application-level identity and platform role.

    Authentication still belongs to Supabase.  This row is the authoritative
    application authorization record; in particular, platform-admin access is
    never inferred from an email address in frontend or request code.
    """

    __tablename__ = "app_accounts"
    __table_args__ = (
        CheckConstraint("system_role in ('user','admin','support')", name="ck_app_account_system_role"),
    )

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    system_role: Mapped[str] = mapped_column(String(16), default="user", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class BusinessPaymentProvider(Base):
    """A provider approved for use by one business.

    Owners select the initial set during onboarding.  After that only a
    platform admin may change it, so the connection screen remains a concise
    reflection of the business's actual providers.
    """

    __tablename__ = "business_payment_providers"
    __table_args__ = (
        CheckConstraint("provider in ('grow','cardcom')", name="ck_business_payment_provider"),
        UniqueConstraint("business_id", "provider", name="uq_business_payment_provider"),
    )

    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), primary_key=True)
    provider: Mapped[str] = mapped_column(String(40), primary_key=True)
    added_by_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

class BusinessOwned:
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"), index=True, default=LEGACY_BUSINESS_ID)
