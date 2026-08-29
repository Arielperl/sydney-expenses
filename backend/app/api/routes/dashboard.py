from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_upload_service
from app.database import get_db
from app.schemas.dashboard import DashboardStats
from app.services.dashboard_service import build_dashboard_stats
from app.services.upload_service import UploadService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    upload_service: UploadService = Depends(get_upload_service),
) -> DashboardStats:
    return build_dashboard_stats(db, upload_service)
