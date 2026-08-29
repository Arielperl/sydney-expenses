from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.system import SystemCapabilities

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/capabilities", response_model=SystemCapabilities)
def get_capabilities() -> SystemCapabilities:
    settings = get_settings()
    provider = settings.receipt_extractor_provider
    mode = "ai" if provider == "openai" else "demo"
    return SystemCapabilities(receipt_extraction_provider=provider, receipt_extraction_mode=mode)
