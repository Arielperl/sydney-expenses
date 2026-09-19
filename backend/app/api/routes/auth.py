"""Supabase Auth gateway. Credentials and refresh tokens never reach browser JS."""
import httpx
from urllib.parse import urlencode
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.core.config import get_settings
from app.core.rate_limit import RateLimiter, client_ip

router = APIRouter(prefix="/auth", tags=["auth"])
ACCESS_COOKIE = "sydney_access"
REFRESH_COOKIE = "sydney_refresh"

# Sensitive-endpoint rate limits — see app/core/rate_limit.py for why these
# are in-process. Login is keyed by both IP and the attempted email so
# neither a single-IP password spray nor a distributed-IP attack against one
# known account gets an unbounded budget.
_signup_by_ip = RateLimiter(max_requests=5, window_seconds=3600)
_login_by_ip = RateLimiter(max_requests=15, window_seconds=300)
_login_by_email = RateLimiter(max_requests=5, window_seconds=900)
_refresh_by_ip = RateLimiter(max_requests=30, window_seconds=300)

class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)
    name: str = Field(default="", max_length=100)

    @field_validator("email")
    @classmethod
    def email_format(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or "." not in value.rsplit("@", 1)[1]:
            raise ValueError("כתובת האימייל אינה תקינה")
        return value

async def auth_request(method: str, path: str, payload=None, token: str | None = None):
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_secret_key:
        raise HTTPException(503, "שירות ההתחברות עדיין לא הוגדר")
    headers = {"apikey": settings.supabase_secret_key}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            result = await client.request(method, settings.supabase_url.rstrip("/") + "/auth/v1/" + path, headers=headers, json=payload)
    except httpx.RequestError:
        raise HTTPException(503, "שירות ההתחברות אינו זמין כרגע. נסו שוב בעוד רגע.")
    if result.status_code >= 400:
        code = result.json().get("error_code", "") if "json" in result.headers.get("content-type", "") else ""
        message = {"email_not_confirmed": "יש לאמת את כתובת האימייל לפני ההתחברות.", "weak_password": "בחרו סיסמה חזקה יותר, באורך שמונה תווים לפחות.", "over_email_send_rate_limit": "נשלחו יותר מדי בקשות. המתינו מספר דקות ונסו שוב.", "signup_disabled": "ההרשמה אינה זמינה כרגע."}.get(code, "לא ניתן להשלים את הבקשה. בדקו את הפרטים ונסו שוב.")
        raise HTTPException(429 if result.status_code == 429 else 401 if result.status_code in (400, 401, 403, 422) else 503, message)
    return result.json() if result.content else {}

def user_view(user):
    from app.database import SessionLocal
    from app.models.business import AppAccount, BusinessMember, Business
    from sqlalchemy import select
    email = (user.get("email") or "").lower()
    verified = bool(user.get("email_confirmed_at"))
    with SessionLocal() as db:
        account = db.get(AppAccount, user["id"]) if verified else None
        if verified:
            display_name = user.get("user_metadata", {}).get("full_name", "")
            if account is None:
                account = AppAccount(user_id=user["id"], email=email, display_name=display_name)
                db.add(account)
            else:
                account.email = email
                account.display_name = display_name
            db.commit()
        member = db.scalar(select(BusinessMember).where(BusinessMember.user_id == user["id"])) if verified else None
        business = db.get(Business, member.business_id) if member else None
        return {"id": user["id"], "email": email, "name": user.get("user_metadata", {}).get("full_name", ""),
                "email_verified": verified, "has_workspace": member is not None,
                "business_name": business.name if business else None, "business_id": member.business_id if member else None,
                "role": member.role if member else None, "system_role": account.system_role if account else "user"}

def set_session(response: Response, data):
    settings = get_settings()
    common = dict(httponly=True, secure=settings.app_environment == "production", samesite="lax")
    response.set_cookie(ACCESS_COOKIE, data["access_token"], max_age=data.get("expires_in", 3600), path="/", **common)
    response.set_cookie(REFRESH_COOKIE, data["refresh_token"], max_age=60*60*24*30, path="/api/auth", **common)
    response.headers["Cache-Control"] = "no-store"

def clear_session(response: Response):
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth")

async def current_user(request: Request):
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise HTTPException(401, "יש להתחבר כדי להמשיך")
    return user_view(await auth_request("GET", "user", token=token))

@router.post("/signup")
async def signup(payload: Credentials, response: Response, request: Request):
    _signup_by_ip.check(f"signup:{client_ip(request)}")
    if len(payload.password) < 8:
        raise HTTPException(422, "הסיסמה צריכה להכיל לפחות שמונה תווים")
    redirect = request.headers.get("origin", "") + "/login"
    data = await auth_request("POST", "signup?" + urlencode({"redirect_to": redirect}), {"email": payload.email, "password": payload.password, "data": {"full_name": payload.name}})
    if data.get("access_token"):
        set_session(response, data)
        return {"user": user_view(data["user"]), "confirmation_required": False}
    return {"user": None, "confirmation_required": True}

@router.post("/login")
async def login(payload: Credentials, response: Response, request: Request):
    _login_by_ip.check(f"login-ip:{client_ip(request)}")
    _login_by_email.check(f"login-email:{payload.email}")
    data = await auth_request("POST", "token?grant_type=password", {"email": payload.email, "password": payload.password})
    set_session(response, data)
    return {"user": user_view(data["user"])}

@router.get("/session")
async def session(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return {"user": await current_user(request)}

@router.post("/refresh")
async def refresh(request: Request, response: Response):
    _refresh_by_ip.check(f"refresh:{client_ip(request)}")
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise HTTPException(401, "יש להתחבר מחדש")
    data = await auth_request("POST", "token?grant_type=refresh_token", {"refresh_token": token})
    set_session(response, data)
    return {"user": user_view(data["user"])}

@router.post("/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get(ACCESS_COOKIE)
    if token:
        try:
            await auth_request("POST", "logout", token=token)
        except HTTPException:
            pass
    clear_session(response)
    return {"ok": True}
