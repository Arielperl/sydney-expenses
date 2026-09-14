import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Numeric, ForeignKey, CheckConstraint
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

class BusinessOwned:
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"), index=True, default=LEGACY_BUSINESS_ID)
