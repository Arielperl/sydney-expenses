from app.api.routes import businesses
from fastapi import APIRouter

from app.api.routes import admin, auth, assistant, connections, dashboard, demo, documents, exceptions, health, imports, sales, support, system, webhooks

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(health.router)
api_router.include_router(sales.router)
api_router.include_router(documents.router)
api_router.include_router(dashboard.router)
api_router.include_router(system.router)
api_router.include_router(assistant.router)
api_router.include_router(exceptions.router)
api_router.include_router(webhooks.router)
api_router.include_router(connections.router)
api_router.include_router(imports.router)
api_router.include_router(demo.router)
api_router.include_router(admin.router)
api_router.include_router(support.router)

api_router.include_router(businesses.router)
