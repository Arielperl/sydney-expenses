from fastapi import APIRouter

from app.api.routes import assistant, dashboard, expenses, health, receipts, reconciliation, system

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(expenses.router)
api_router.include_router(receipts.router)
api_router.include_router(dashboard.router)
api_router.include_router(system.router)
api_router.include_router(assistant.router)
api_router.include_router(reconciliation.router)
