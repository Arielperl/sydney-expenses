import io
import logging
import time
from base64 import b64encode
from datetime import date as date_type
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
from app.services.extraction.image_preprocessing import generate_variants
from app.services.extraction.merge import drop_resolved_not_confident_warnings, merge_receipt_fields
from app.services.extraction.ocr_selection import run_ocr_candidates
from app.services.extraction.prompts import build_ocr_assisted_prompt
from app.services.extraction.receipt_parser import ParsedReceiptCandidates, parse_receipt_candidates
from app.services.extraction.sanitization import sanitize_extracted_fields, to_decimal

logger = logging.getLogger(__name__)

_HINT_FIELDS = ("business_name", "receipt_number", "date", "total", "vat", "currency")


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


def _parse_iso_date(date_str: str | None) -> tuple[date_type | None, str | None]:
    """Parses the model's own date string (expected ISO format).

    Returns (value, warning). A missing date_str is not itself a warning here
    (nullable fields simply flow through to the merge step); an unparseable or
    future-dated string is invalid model output and is flagged immediately,
    matching the previous behavior before this parsing moved out of
    sanitize_extracted_fields."""
    if not date_str:
        return None, None
    try:
        parsed = date_type.fromisoformat(date_str)
    except ValueError:
        return None, "date_not_confident"
    if parsed > date_type.today():
        return None, "date_not_confident"
    return parsed, None


def _build_prompt_hints(candidates: ParsedReceiptCandidates) -> dict[str, tuple[object, str]]:
    """Only high/medium-confidence deterministic candidates are shown to the
    model as hints — a low-confidence guess (e.g. a shaky merchant-name match)
    is never presented as if it were reliable reference data."""
    hints: dict[str, tuple[object, str]] = {}
    for field in _HINT_FIELDS:
        candidate = getattr(candidates, field)
        if candidate is not None and candidate.confidence in ("high", "medium"):
            hints[field] = (candidate.value, candidate.confidence)
    return hints


class LocalReceiptExtractor(ReceiptExtractor):
    """Extracts receipt data fully locally: Tesseract OCR (heb+eng) plus a local
    Ollama vision model (default gemma3:12b), with no external network call and no
    per-request cost. Every field is re-validated with the same business rules as
    the other providers (sanitize_extracted_fields) — nothing from the model is
    trusted as-is.

    A deterministic, regex-based parser (receipt_parser.py) also scans the OCR
    text for structurally labeled values (a total next to "לתשלום", a VAT amount
    next to "מע\"מ", a date, etc.) and a merge policy (merge.py) combines those
    candidates with the model's own output: a confident parser match fills a gap
    the model left null, and a genuine disagreement between the two is surfaced
    as a warning rather than silently resolved either way.

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

        best_ocr_text, ranked_ocr_texts, enhanced_image, ocr_warning = self._run_ocr(path)
        candidates = parse_receipt_candidates(ranked_ocr_texts) if ranked_ocr_texts else ParsedReceiptCandidates()
        prompt_hints = _build_prompt_hints(candidates)

        images_b64 = [b64encode(path.read_bytes()).decode("ascii")]
        if enhanced_image is not None:
            # A second, upscaled/enhanced image alongside the original often
            # helps the model read small or low-contrast text (e.g. a
            # merchant name) that the original narrow photo makes illegible —
            # bounded to exactly one extra image, never several.
            buffer = io.BytesIO()
            enhanced_image.convert("RGB").save(buffer, format="PNG")
            images_b64.append(b64encode(buffer.getvalue()).decode("ascii"))

        payload = {
            "model": self._settings.ollama_receipt_model,
            "prompt": build_ocr_assisted_prompt(
                best_ocr_text, prompt_hints, has_enhanced_image=enhanced_image is not None
            ),
            "images": images_b64,
            "stream": False,
            "format": _RawLocalExtraction.model_json_schema(),
        }

        raw = self._generate_with_retries(client, payload)

        extra_warnings = list(raw.warnings)
        if ocr_warning:
            extra_warnings.append(ocr_warning)
        category = self._coerce_category(raw.category, extra_warnings)

        model_date, date_warning = _parse_iso_date(raw.date)
        if date_warning:
            extra_warnings.append(date_warning)

        merged = merge_receipt_fields(
            business_name=raw.business_name,
            receipt_number=raw.receipt_number,
            date=model_date,
            total=to_decimal(raw.total),
            vat=to_decimal(raw.vat),
            currency=raw.currency,
            candidates=candidates,
        )
        for field_result in (
            merged.business_name,
            merged.receipt_number,
            merged.date,
            merged.total,
            merged.vat,
            merged.currency,
        ):
            extra_warnings.extend(field_result.warnings)

        extra_warnings = drop_resolved_not_confident_warnings(extra_warnings, merged)

        return sanitize_extracted_fields(
            business_name=merged.business_name.value,
            receipt_number=merged.receipt_number.value,
            date_str=merged.date.value.isoformat() if merged.date.value else None,
            total_raw=float(merged.total.value) if merged.total.value is not None else None,
            vat_raw=float(merged.vat.value) if merged.vat.value is not None else None,
            currency_raw=merged.currency.value,
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

    def _run_ocr(self, path: Path) -> tuple[str, list[str], Image.Image | None, str | None]:
        if pytesseract is None:
            return "", [], None, "ocr_unavailable"
        try:
            with Image.open(path) as image:
                variants = generate_variants(image)
                candidates = run_ocr_candidates(variants, self._settings.tesseract_languages)
                enhanced_image = variants["enhanced"].copy()  # image closes on exit; keep our own copy
            if not candidates:
                return "", [], enhanced_image, "ocr_unavailable"
            ranked_texts = [c.text for c in sorted(candidates, key=lambda c: -c.score)]
            return ranked_texts[0], ranked_texts, enhanced_image, None
        except Exception:  # noqa: BLE001 - OCR is best-effort; any failure falls back to image-only
            logger.info("receipt_ocr result=failure")  # safe: no text/image content logged
            return "", [], None, "ocr_unavailable"
