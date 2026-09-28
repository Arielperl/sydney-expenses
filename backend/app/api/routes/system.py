import shutil

import httpx
from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.system import SystemCapabilities

router = APIRouter(prefix="/system", tags=["system"])


def _check_ollama_reachable(base_url: str) -> bool:
    try:
        with httpx.Client(timeout=1.0) as client:
            response = client.get(f"{base_url}/api/version")
            return response.status_code == 200
    except httpx.HTTPError:
        return False


def _tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


@router.get("/capabilities", response_model=SystemCapabilities)
def get_capabilities() -> SystemCapabilities:
    settings = get_settings()
    provider = settings.receipt_extractor_provider

    if provider == "openai":
        mode = "ai"
    elif provider == "local":
        mode = "local"
    else:
        mode = "demo"

    ollama_available = None
    tesseract_available = None
    if provider == "local":
        ollama_available = _check_ollama_reachable(settings.ollama_base_url)
        tesseract_available = _tesseract_available()

    return SystemCapabilities(
        receipt_extraction_provider=provider,
        receipt_extraction_mode=mode,
        real_ai_enabled=provider in ("local", "openai"),
        ollama_available=ollama_available,
        tesseract_available=tesseract_available,
    )
