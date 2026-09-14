from pathlib import Path
import re

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from app.api.routes.auth import current_user
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.router import api_router
from app.core.config import get_settings, validate_auth_settings, validate_storage_settings

settings = get_settings()
validate_storage_settings(settings)
validate_auth_settings(settings)

Path(settings.uploads_dir).mkdir(parents=True, exist_ok=True)

_is_production = settings.app_environment == "production"

# The interactive API docs (Swagger/ReDoc) and raw OpenAPI schema are not
# gated by `protect_workspace` below — they're served at the app root
# (/docs, /redoc, /openapi.json), not under /api/, so the middleware's
# path.startswith("/api/") check never even applies to them. They're
# genuinely useful in development, but in production they'd publicly expose
# the full API surface (every route, schema, and field name) to anyone,
# authenticated or not, which is unnecessary information disclosure with no
# corresponding product benefit.
app = FastAPI(
    title=settings.app_name,
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    openapi_url=None if _is_production else "/openapi.json",
)


@app.get("/", include_in_schema=False)
def open_product() -> RedirectResponse:
    """Send people who open the API hostname to the public web app."""
    return RedirectResponse(url=settings.cors_allowed_origins[0], status_code=307)

@app.middleware("http")
async def protect_workspace(request: Request, call_next):
    path = request.url.path
    config = get_settings()
    # Webhooks keep their own timestamp/HMAC validation and never use browser cookies.
    # Matches both a demo-pay connection's stable `id` (a UUID) and a
    # URL-token provider's `url_token` (e.g. Grow — a `secrets.token_urlsafe`
    # value, not UUID-shaped) — see IntegrationConnection's docstring for why
    # two different path shapes exist.
    webhook = path == "/api/webhooks/payments" or bool(
        re.fullmatch(r"/api/webhooks/connections/[0-9a-zA-Z_-]{20,64}", path)
    )
    if webhook:
        from app.models.business import LEGACY_BUSINESS_ID
        request.state.business_id = LEGACY_BUSINESS_ID
    if config.auth_required and request.method != "OPTIONS":
        if request.method not in ("GET", "HEAD") and not webhook:
            if request.headers.get("origin") not in config.cors_allowed_origins:
                return JSONResponse({"detail": "מקור הבקשה אינו מורשה"}, status_code=403)
        onboarding = path == "/api/businesses" and request.method == "POST"
        protected = (
            path.startswith("/api/")
            and path != "/api/health"
            and not path.startswith("/api/auth/")
            and not webhook
            and not onboarding
        ) or path.startswith("/uploads/")
        if protected:
            try:
                user = await current_user(request)
                if not user["has_workspace"]:
                    raise HTTPException(403, "החשבון עדיין לא שויך לעסק")
                request.state.user = user
                request.state.business_id = user["business_id"]
                if user["role"] == "viewer" and request.method not in ("GET", "HEAD") and path != "/api/assistant/chat":
                    raise HTTPException(403, "ההרשאה שלך מאפשרת צפייה בלבד")
                if path.startswith("/uploads/"):
                    from app.database import SessionLocal
                    from app.models.sale import Sale
                    from sqlalchemy import select
                    with SessionLocal() as db:
                        allowed = db.scalar(select(Sale.id).where(Sale.business_id == user["business_id"], Sale.document_url == path))
                    if not allowed:
                        raise HTTPException(404, "המסמך לא נמצא")
            except HTTPException as error:
                return JSONResponse({"detail": error.detail}, status_code=error.status_code)
    response = await call_next(request)
    if path.startswith("/api/auth/") or path.startswith("/uploads/") or path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response

# Registered AFTER protect_workspace so it wraps OUTSIDE it (Starlette/FastAPI
# middleware order: the last one added runs first on the way in and last on
# the way out) — that's what makes these headers land on EVERY response,
# including protect_workspace's own early 401/403 rejections, which return
# before ever calling further down the chain. Registering this middleware
# first would mean it never runs at all for those early-rejected responses.
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    # Baseline hardening headers for every response — cheap and broadly supported.
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Clickjacking protection: both the legacy header (older browsers) and
    # the modern CSP directive (which takes precedence where supported).
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
        if _is_production
        else "frame-ancestors 'none'"
    )
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
    if _is_production:
        # Only meaningful — and only sent — over HTTPS, which production is
        # assumed to terminate at (see validate_auth_settings: production
        # requires https:// CORS origins). Sending this over plain HTTP in
        # development would be actively misleading.
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

app.include_router(api_router)
app.mount("/uploads", StaticFiles(directory=settings.uploads_dir), name="uploads")
