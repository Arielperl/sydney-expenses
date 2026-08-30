import os
import shutil
import tempfile
from pathlib import Path

import pytest

_TEST_DIR = Path(tempfile.mkdtemp(prefix="receiptly-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DIR / 'test.db'}"
os.environ["UPLOADS_DIR"] = str(_TEST_DIR / "uploads")
# The test suite must never depend on real Supabase credentials, even when the
# developer's own backend/.env is configured for STORAGE_PROVIDER=supabase.
# Tests that exercise SupabaseReceiptStorage do so against a fake client instead.
os.environ["STORAGE_PROVIDER"] = "local"
# Likewise, never let a developer's own RECEIPT_EXTRACTOR_PROVIDER (e.g. "local" or
# "openai") leak into the suite — tests that want a specific provider set it explicitly.
os.environ["RECEIPT_EXTRACTOR_PROVIDER"] = "mock"

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _clean_uploads():
    uploads_dir = Path(os.environ["UPLOADS_DIR"])
    yield
    if uploads_dir.exists():
        shutil.rmtree(uploads_dir)
    uploads_dir.mkdir(parents=True, exist_ok=True)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client


# A genuine 2x2 PNG, generated via Pillow itself, so it passes real image verification.
VALID_PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000002000000020802000000fdd49a73"
    "0000001049444154789c63fccf00024c609201000d1d010382c971ff0000000049454e44ae426082"
)

