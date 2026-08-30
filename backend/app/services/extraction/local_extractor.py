import logging
import time
from base64 import b64encode
from pathlib import Path

import httpx
from PIL import Image
from pydantic import BaseModel, ValidationError

try:
    import pytesseract
except ImportError:  # pragma: no cover - pytesseract is a declared dependency
    pytesseract = None  # type: ignore[assignment]

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
from app.services.extraction.image_preprocessing import preprocess_for_ocr
from app.services.extraction.prompts import build_ocr_assisted_prompt
from app.services.extraction.sanitization import sanitize_extracted_fields

logger = logging.getLogger(__name__)


class _RawLocalExtraction(BaseModel):
    """Structured-output target for the local model. Fields carry defaults (unlike
    the OpenAI strict-mode schema) since Ollama's JSON-schema-constrained decoding
    is lenient about omitted keys — any gap just falls back to these safe defaults,
    which sanitize_extracted_fields() then treats the same as an explicit null."""

    business_name: str | None = None
    receipt_number: str | None = None
    date: str | None = None
    total: float | None = None
    vat: float | None = None
    currency: str = "ILS"
    # Plain str, not the ExpenseCategory enum: a local, quantized model's JSON-schema-
    # constrained decoding is less rigorously enforced than a hosted provider's true
    # strict structured outputs, so an out-of-enum value must degrade gracefully
    # (see _coerce_category) instead of failing the whole extraction.
    category: str = ExpenseCategory.OTHER.value
    warnings: list[str] = []


class LocalReceiptExtractor(ReceiptExtractor):
    """Extracts receipt data fully locally: Tesseract OCR (heb+eng) plus a local
    Ollama vision model (default gemma3:12b), with no external network call and no
    per-request cost. Every field is re-validated with the same business rules as
    the other providers (sanitize_extracted_fields) — nothing from the model is
    trusted as-is.

    If Tesseract fails, extraction continues with the image alone (a warning is
    added) rather than failing outright — the vision model can often still read
    the receipt without OCR assistance.

    Retries are bounded and explicit, applied only to transient failures (timeouts,
    connection errors, 5xx). Non-transient errors (4xx, malformed output) fail
    immediately with no retry.
    """

    _retry_backoff_base_seconds: float = 0.5

    def __init__(self, settings: Settings, http_client: httpx.Client | None = None):
        self._settings = settings
        self._http_client = http_client

    def _client(self) -> httpx.Client:
        if not self._settings.ollama_receipt_model:
            raise ReceiptExtractionConfigError(
                "RECEIPT_EXTRACTOR_PROVIDER is 'local' but OLLAMA_RECEIPT_MODEL is not configured."
            )
        if self._http_client is None:
            self._http_client = httpx.Client(
                base_url=self._settings.ollama_base_url,
                timeout=self._settings.ollama_timeout_seconds,
            )
        return self._http_client

    def extract(self, image_path: str) -> ExtractedReceiptData:
        client = self._client()
        path = Path(image_path)

        ocr_text, ocr_warning = self._run_ocr(path)
        image_b64 = b64encode(path.read_bytes()).decode("ascii")

        payload = {
            "model": self._settings.ollama_receipt_model,
            "prompt": build_ocr_assisted_prompt(ocr_text),
            "images": [image_b64],
            "stream": False,
            "format": _RawLocalExtraction.model_json_schema(),
        }

        raw = self._generate_with_retries(client, payload)

        extra_warnings = list(raw.warnings)
        if ocr_warning:
            extra_warnings.append(ocr_warning)
        category = self._coerce_category(raw.category, extra_warnings)

        return sanitize_extracted_fields(
            business_name=raw.business_name,
            receipt_number=raw.receipt_number,
            date_str=raw.date,
            total_raw=raw.total,
            vat_raw=raw.vat,
            currency_raw=raw.currency,
            category=category,
            warnings=extra_warnings,
        )

    @staticmethod
    def _coerce_category(raw_category: str, warnings: list[str]) -> ExpenseCategory:
        try:
            return ExpenseCategory(raw_category)
        except ValueError:
            if "category_not_confident" not in warnings:
                warnings.append("category_not_confident")
            return ExpenseCategory.OTHER

    def _generate_with_retries(self, client: httpx.Client, payload: dict) -> _RawLocalExtraction:
        max_retries = self._settings.ollama_max_retries
        attempt = 0

        while True:
            try:
                response = client.post("/api/generate", json=payload)
                response.raise_for_status()
                break
            except httpx.TimeoutException as exc:
                if attempt >= max_retries:
                    raise ReceiptExtractionTimeoutError(
                        f"Local model extraction timed out after {attempt + 1} attempt(s)."
                    ) from exc
                attempt += 1
                time.sleep(self._backoff_seconds(attempt))
            except httpx.ConnectError as exc:
                if attempt >= max_retries:
                    raise ReceiptExtractionProviderError(
                        "Could not reach Ollama. Is it running? (ollama serve)"
                    ) from exc
                attempt += 1
                time.sleep(self._backoff_seconds(attempt))
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code >= 500 and attempt < max_retries:
                    attempt += 1
                    time.sleep(self._backoff_seconds(attempt))
                    continue
                raise ReceiptExtractionProviderError(
                    f"Ollama returned an error (status {exc.response.status_code})."
                ) from exc

        try:
            body = response.json()
        except ValueError as exc:
            raise ReceiptExtractionParsingError("Ollama returned a non-JSON response.") from exc

        raw_text = body.get("response")
        if not raw_text:
            raise ReceiptExtractionParsingError("The local model returned no structured output.")

        try:
            return _RawLocalExtraction.model_validate_json(raw_text)
        except ValidationError as exc:
            raise ReceiptExtractionParsingError("Could not parse the local model's structured output.") from exc

    def _backoff_seconds(self, attempt: int) -> float:
        return min(self._retry_backoff_base_seconds * (2**attempt), 5)

    def _run_ocr(self, path: Path) -> tuple[str, str | None]:
        if pytesseract is None:
            return "", "ocr_unavailable"
        try:
            with Image.open(path) as image:
                preprocessed = preprocess_for_ocr(image)
                text = pytesseract.image_to_string(preprocessed, lang=self._settings.tesseract_languages)
            return text.strip(), None
        except Exception:  # noqa: BLE001 - OCR is best-effort; any failure falls back to image-only
            logger.info("receipt_ocr result=failure")  # safe: no text/image content logged
            return "", "ocr_unavailable"
