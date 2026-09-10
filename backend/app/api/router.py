from fastapi import APIRouter

from app.api.routes import assistant, dashboard, documents, exceptions, health, imports, sales, system, webhooks

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(sales.router)
api_router.include_router(documents.router)
api_router.include_router(dashboard.router)
api_router.include_router(system.router)
api_router.include_router(assistant.router)
api_router.include_router(exceptions.router)
api_router.include_router(webhooks.router)
api_router.include_router(imports.router)
