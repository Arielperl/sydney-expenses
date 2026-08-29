from fastapi import APIRouter

from app.api.routes import dashboard, expenses, health, receipts

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(expenses.router)
api_router.include_router(receipts.router)
api_router.include_router(dashboard.router)
