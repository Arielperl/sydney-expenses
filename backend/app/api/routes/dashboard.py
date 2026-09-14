from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.dashboard import DashboardPeriodName, DashboardStats
from app.services.dashboard_service import InvalidDashboardPeriodError, build_dashboard_stats

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(
    period: DashboardPeriodName = Query(default="this_month"),
    custom_start: date | None = Query(default=None),
    custom_end: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> DashboardStats:
    try:
        return build_dashboard_stats(db, period=period, custom_start=custom_start, custom_end=custom_end)
    except InvalidDashboardPeriodError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
