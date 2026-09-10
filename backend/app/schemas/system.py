from typing import Literal

from pydantic import BaseModel


class SystemCapabilities(BaseModel):
    """Non-sensitive provider capability info for the frontend's provider-status badge.

    Never include keys, secrets, filesystem paths, or any other configuration value.
    """

    receipt_extraction_provider: Literal["mock", "local", "openai"]
    receipt_extraction_mode: Literal["demo", "local", "ai"]
    real_ai_enabled: bool
    ollama_available: bool | None = None
    tesseract_available: bool | None = None
    # Gates the in-product demo simulator's UI (scenario picker + reset
    # action) — the frontend must hide/disable that UI when this is false,
    # matching the backend's own app_environment gate on /api/demo/*.
    demo_simulator_enabled: bool = True
