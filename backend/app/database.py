from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings
from fastapi import Request, HTTPException

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db(request: Request) -> Generator[Session, None, None]:
    from app.models.business import LEGACY_BUSINESS_ID
    from app.core import tenant  # register ORM guards
    db = SessionLocal()
    business_id = getattr(request.state, "business_id", None)
    if not business_id and get_settings().auth_required:
        db.close()
        raise HTTPException(403, "לא נבחר עסק מורשה")
    db.info["business_id"] = business_id or LEGACY_BUSINESS_ID
    try:
        yield db
    finally:
        db.close()
