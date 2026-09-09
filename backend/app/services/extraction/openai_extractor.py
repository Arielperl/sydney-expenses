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
from app.services.extraction.image_preprocessing import generate_variants_with_detection
from app.services.extraction.merge import drop_resolved_not_confident_warnings, merge_receipt_fields
from app.services.extraction.ocr_selection import build_ocr_summary, run_ocr_candidates
from app.services.extraction.prompts import build_ocr_assisted_prompt
from app.services.extraction.receipt_parser import (
    ParsedReceiptCandidates,
    infer_category_from_merchant_name,
    parse_receipt_candidates,
)
from app.services.extraction.sanitization import sanitize_extracted_fields, to_decimal

try:
    import pytesseract
except ImportError:  # pragma: no cover - pytesseract is a declared dependency
    pytesseract = None  # type: ignore[assignment]

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

_HINT_FIELDS = ("business_name", "receipt_number", "date", "total", "vat", "currency")


def _build_prompt_hints(candidates: ParsedReceiptCandidates) -> dict[str, tuple[object, str]]:
    """Only high/medium-confidence deterministic candidates are shown to the
    model as hints — see local_extractor.py for the identical policy this
    mirrors, kept as a separate small copy here rather than a shared import
    so the two providers' extraction paths stay independently readable."""
    hints: dict[str, tuple[object, str]] = {}
    for field in _HINT_FIELDS:
        candidate = getattr(candidates, field)
        if candidate is not None and candidate.confidence in ("high", "medium"):
            hints[field] = (candidate.value, candidate.confidence)
    return hints


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

    Also runs the same local, deterministic OCR/spatial-parser pass the local
    (Ollama) provider uses (see receipt_parser.py) — a real, evaluation-measured
    gap found after this provider originally only sent the raw image with no
    OCR assist at all: on the private evaluation set, several factual fields
    (date, VAT, receipt_number, business_name) came back meaningfully *less*
    accurate than the local provider specifically because of this missing
    assist, even though the OpenAI model itself is materially faster and more
    reliable overall. The same merge policy applies: a confident parser match
    fills a gap the model left null, and a high-confidence parser value can
    never be silently overridden by a differing model guess (merge.py).

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
        path = Path(image_path)
        data_url = self._encode_image(image_path)

        ocr_summary, candidates, ocr_warning = self._run_ocr(path)
        prompt_hints = _build_prompt_hints(candidates)
        prompt = build_ocr_assisted_prompt(ocr_summary, prompt_hints)

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
                                {"type": "input_text", "text": prompt},
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
                break
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

        extra_warnings = list(raw.warnings)
        if ocr_warning:
            extra_warnings.append(ocr_warning)

        model_date, date_warning = self._parse_iso_date(raw.date)
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

        category = raw.category
        if category == ExpenseCategory.OTHER:
            inferred_category = infer_category_from_merchant_name(merged.business_name.value)
            if inferred_category is not None:
                category = inferred_category
                extra_warnings.append("category_from_merchant_name")

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
    def _parse_iso_date(date_str: str | None):
        from datetime import date as date_type

        if not date_str:
            return None, None
        try:
            parsed = date_type.fromisoformat(date_str)
        except ValueError:
            return None, "date_not_confident"
        if parsed > date_type.today():
            return None, "date_not_confident"
        return parsed, None

    def _backoff_seconds(self, attempt: int) -> float:
        return min(self._retry_backoff_base_seconds * (2**attempt), 5)

    def _run_ocr(self, path: Path) -> tuple[str, ParsedReceiptCandidates, str | None]:
        """Best-effort local OCR/parser pass — the same deterministic hint
        source local_extractor.py uses. Any failure degrades to "no hints"
        rather than blocking the OpenAI call, since the vision model alone
        can often still read the receipt without OCR assistance."""
        if pytesseract is None:
            return "", ParsedReceiptCandidates(), "ocr_unavailable"
        try:
            from PIL import Image

            with Image.open(path) as image:
                variants, _detection = generate_variants_with_detection(image)
                ocr_candidates = run_ocr_candidates(variants, self._settings.tesseract_languages)
            if not ocr_candidates:
                return "", ParsedReceiptCandidates(), "ocr_unavailable"
            ranked = sorted(ocr_candidates, key=lambda c: -c.score)
            ranked_lines = [c.lines for c in ranked]
            summary = build_ocr_summary(ranked[0].lines)
            candidates = parse_receipt_candidates(ranked_lines)
            return summary, candidates, None
        except Exception:  # noqa: BLE001 - OCR is best-effort; any failure falls back to image-only
            logger.info("receipt_ocr result=failure")  # safe: no text/image content logged
            return "", ParsedReceiptCandidates(), "ocr_unavailable"

    @staticmethod
    def _encode_image(image_path: str) -> str:
        path = Path(image_path)
        mime = _MIME_BY_EXTENSION.get(path.suffix.lower(), "image/jpeg")
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{encoded}"
