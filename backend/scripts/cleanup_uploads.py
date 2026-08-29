"""Removes stale pending receipt uploads and their orphaned files.

Run manually or on a schedule (e.g. a daily cron job):

    cd backend && source .venv/bin/activate && python -m scripts.cleanup_uploads
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.deps import get_upload_service  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.services.receipt_lifecycle_service import cleanup_expired_uploads  # noqa: E402


def main() -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        cleaned = cleanup_expired_uploads(db, get_upload_service(), settings.pending_upload_expiry_hours)
        print(f"Marked {cleaned} pending upload(s) older than {settings.pending_upload_expiry_hours}h as expired.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
