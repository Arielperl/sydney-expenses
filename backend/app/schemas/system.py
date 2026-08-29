from typing import Literal

from pydantic import BaseModel


class SystemCapabilities(BaseModel):
    """Non-sensitive provider capability info for the frontend's provider-status badge.

    Never include keys, secrets, or any other environment configuration values here.
    """

    receipt_extraction_provider: Literal["mock", "openai"]
    receipt_extraction_mode: Literal["demo", "ai"]
