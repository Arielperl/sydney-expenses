import base64
import logging
import time
from pathlib import Path

from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)
from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.models.expense import ExpenseCategory
from app.schemas.receipt import ExtractedReceiptData
from app.services.extraction.base import ReceiptExtractor
from app.services.extraction.exceptions import (
    ReceiptExtractionConfigError,
    ReceiptExtractionParsingError,
    ReceiptExtractionProviderError,
    ReceiptExtractionTimeoutError,
)
from app.services.extraction.prompts import RECEIPT_EXTRACTION_INSTRUCTIONS
from app.services.extraction.sanitization import sanitize_extracted_fields

logger = logging.getLogger(__name__)

_MIME_BY_EXTENSION = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

_TRANSIENT_TIMEOUT_ERRORS = (APITimeoutError,)
_TRANSIENT_RETRYABLE_ERRORS = (APIConnectionError, RateLimitError, InternalServerError)
_NON_TRANSIENT_ERRORS = (BadRequestError, AuthenticationError, PermissionDeniedError, NotFoundError)


class _RawReceiptExtraction(BaseModel):
    """Structured-output target. Every field is required-but-nullable (strict mode),
    so the model must always return an explicit value or null, never omit a key."""

    business_name: str | None
    receipt_number: str | None
    date: str | None
    total: float | None
    vat: float | None
    currency: str
    category: ExpenseCategory
    warnings: list[str]


class OpenAIReceiptExtractor(ReceiptExtractor):
    """Extracts receipt data via the OpenAI Responses API using strict Structured Outputs.

    Configuration is validated lazily, on first use, rather than at construction time —
    this lets `get_receipt_extractor()` build the object unconditionally, so a missing
    key surfaces as a normal (caught) extraction failure the upload route already
    handles gracefully, instead of an unhandled dependency-injection error.

    Retries are bounded and explicit, applied only to transient failures (timeouts,
    connection errors, rate limits, 5xx). Anything else (bad request, auth, not found)
    fails immediately with no retry.
    """

    # Exposed as a class attribute (rather than a hardcoded literal) so tests can
    # monkeypatch it to 0 and exercise the bounded-retry logic without real waits.
    _retry_backoff_base_seconds: float = 0.5

    def __init__(self, settings: Settings, client: OpenAI | None = None):
        self._settings = settings
        self._client = client

    def _client_or_raise(self) -> OpenAI:
        if not self._settings.openai_api_key:
            raise ReceiptExtractionConfigError(
                "RECEIPT_EXTRACTOR_PROVIDER is 'openai' but OPENAI_API_KEY is not configured."
            )
        if not self._settings.openai_receipt_model:
            raise ReceiptExtractionConfigError(
                "RECEIPT_EXTRACTOR_PROVIDER is 'openai' but OPENAI_RECEIPT_MODEL is not configured."
            )
        if self._client is None:
            # max_retries=0: this class retries explicitly (see extract()) so retry
            # behavior stays bounded, transient-only, and directly testable.
            self._client = OpenAI(api_key=self._settings.openai_api_key, max_retries=0)
        return self._client

    def extract(self, image_path: str) -> ExtractedReceiptData:
        client = self._client_or_raise()
        data_url = self._encode_image(image_path)
        max_retries = self._settings.openai_max_retries
        attempt = 0

        while True:
            try:
                response = client.responses.parse(
                    model=self._settings.openai_receipt_model,
                    input=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "input_text", "text": RECEIPT_EXTRACTION_INSTRUCTIONS},
                                {"type": "input_image", "image_url": data_url},
                            ],
                        }
                    ],
                    text_format=_RawReceiptExtraction,
                    store=False,
                    timeout=self._settings.openai_timeout_seconds,
                )
                raw = response.output_parsed
                if raw is None:
                    raise ReceiptExtractionParsingError("The model returned no parsed structured output.")
                return sanitize_extracted_fields(
                    business_name=raw.business_name,
                    receipt_number=raw.receipt_number,
                    date_str=raw.date,
                    total_raw=raw.total,
                    vat_raw=raw.vat,
                    currency_raw=raw.currency,
                    category=raw.category,
                    warnings=raw.warnings,
                )
            except _TRANSIENT_TIMEOUT_ERRORS as exc:
                if attempt >= max_retries:
                    raise ReceiptExtractionTimeoutError(
                        f"Receipt extraction timed out after {attempt + 1} attempt(s)."
                    ) from exc
                attempt += 1
                time.sleep(self._backoff_seconds(attempt))
            except _TRANSIENT_RETRYABLE_ERRORS as exc:
                if attempt >= max_retries:
                    raise ReceiptExtractionProviderError(
                        f"Receipt extraction provider failed after {attempt + 1} attempt(s): "
                        f"{type(exc).__name__}"
                    ) from exc
                attempt += 1
                time.sleep(self._backoff_seconds(attempt))
            except _NON_TRANSIENT_ERRORS as exc:
                raise ReceiptExtractionProviderError(
                    f"Receipt extraction provider error: {type(exc).__name__}"
                ) from exc
            except ValidationError as exc:
                raise ReceiptExtractionParsingError("Could not parse the model's structured output.") from exc

    def _backoff_seconds(self, attempt: int) -> float:
        return min(self._retry_backoff_base_seconds * (2**attempt), 5)

    @staticmethod
    def _encode_image(image_path: str) -> str:
        path = Path(image_path)
        mime = _MIME_BY_EXTENSION.get(path.suffix.lower(), "image/jpeg")
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{encoded}"
