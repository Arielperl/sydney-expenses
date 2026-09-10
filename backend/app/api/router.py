from fastapi import APIRouter

from app.api.routes import assistant, dashboard, expenses, health, imports, receipts, reconciliation, system, webhooks

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(expenses.router)
api_router.include_router(receipts.router)
api_router.include_router(dashboard.router)
api_router.include_router(system.router)
api_router.include_router(assistant.router)
api_router.include_router(reconciliation.router)
api_router.include_router(webhooks.router)
api_router.include_router(imports.router)
