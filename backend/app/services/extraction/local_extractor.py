import io
import logging
import time
from base64 import b64encode
from dataclasses import dataclass, field
from datetime import date as date_type
from pathlib import Path

import httpx
from PIL import Image
from pydantic import BaseModel, ValidationError, create_model

try:
    import pytesseract
except ImportError:  # pragma: no cover - pytesseract is a declared dependency
    pytesseract = None  # type: ignore[assignment]

from app.core.config import Settings
from app.models.expense import ExpenseCategory
from app.schemas.receipt import ExtractedReceiptData
from app.services.extraction.base import ReceiptExtractor
from app.services.extraction.document_geometry import DocumentDetection
from app.services.extraction.exceptions import (
    ReceiptExtractionConfigError,
    ReceiptExtractionParsingError,
    ReceiptExtractionProviderError,
    ReceiptExtractionTimeoutError,
)
from app.services.extraction.image_preprocessing import generate_variants_with_detection
from app.services.extraction.merge import drop_resolved_not_confident_warnings, merge_receipt_fields
from app.services.extraction.ocr_selection import OcrLine, build_ocr_summary, run_ocr_candidates
from app.services.extraction.prompts import build_ocr_assisted_prompt
from app.services.extraction.receipt_parser import (
    ParsedReceiptCandidates,
    infer_category_from_merchant_name,
    parse_receipt_candidates,
)
from app.services.extraction.sanitization import sanitize_extracted_fields, to_decimal

logger = logging.getLogger(__name__)

_HINT_FIELDS = ("business_name", "receipt_number", "date", "total", "vat", "currency")

# The "factual" fields a deterministic OCR/spatial-parser pass can resolve on
# its own, given a clearly labeled receipt — as opposed to business_name and
# category, which stay "semantic" fields always asked of the vision model
# (see _build_response_model). Order matters only for prompt readability.
_FACTUAL_FIELDS = ("receipt_number", "date", "total", "vat", "currency")

_FACTUAL_FIELD_SPECS: dict[str, tuple[type, object]] = {
    "receipt_number": (str | None, None),
    "date": (str | None, None),
    "total": (float | None, None),
    "vat": (float | None, None),
    "currency": (str, "ILS"),
}

# Plain str, not the ExpenseCategory enum, for category: a local, quantized
# model's JSON-schema-constrained decoding is less rigorously enforced than a
# hosted provider's true strict structured outputs, so an out-of-enum value
# must degrade gracefully (see _coerce_category) instead of failing the whole
# extraction. Always requested — no deterministic signal is trusted enough on
# its own to skip asking the vision model about merchant name or category.
_SEMANTIC_FIELD_SPECS: dict[str, tuple[type, object]] = {
    "business_name": (str | None, None),
    "category": (str, ExpenseCategory.OTHER.value),
    "warnings": (list[str], []),
}


def _build_response_model(unresolved_factual_fields: tuple[str, ...]) -> type[BaseModel]:
    """Builds a structured-output schema containing only the factual fields
    the deterministic parser did NOT confidently (high-confidence) resolve,
    plus the two fields always asked of the model (business_name, category).

    A field the parser already resolved with high confidence is dropped from
    the schema entirely, not merely de-emphasized in the prompt: Ollama's
    JSON-schema-constrained decoding then cannot produce that key at all, so a
    stochastic model guess can never even be offered as a conflicting value
    for it, and the model spends no generation time reasoning about or
    emitting it either — this is what makes the deterministic parser's high-
    confidence reads immune to being overwritten, not just policy-preferred
    over a weaker model answer (compare merge.merge_field's tie-break, which
    still applies for any field that IS asked and disagrees)."""
    fields: dict[str, tuple[type, object]] = {
        name: _FACTUAL_FIELD_SPECS[name] for name in _FACTUAL_FIELDS if name in unresolved_factual_fields
    }
    fields.update(_SEMANTIC_FIELD_SPECS)
    return create_model("_RawLocalExtraction", **fields)


@dataclass(frozen=True)
class _OcrExtractionResult:
    """Everything the OCR/spatial-parsing stage hands back to extract()."""

    summary_text: str = ""
    ranked_lines: list[tuple[OcrLine, ...]] = field(default_factory=list)
    detection: DocumentDetection = field(default_factory=DocumentDetection)
    vision_image: Image.Image | None = None
    warning: str | None = None


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

        ocr_result = self._run_ocr(path)
        candidates = (
            parse_receipt_candidates(ocr_result.ranked_lines) if ocr_result.ranked_lines else ParsedReceiptCandidates()
        )

        # Deterministic-first: a factual field the parser resolved with high
        # confidence is dropped from what the model is even asked for (see
        # _build_response_model) — never merely "preferred" after the fact.
        resolved_factual_fields = {
            name for name in _FACTUAL_FIELDS if (c := getattr(candidates, name)) is not None and c.confidence == "high"
        }
        unresolved_factual_fields = tuple(name for name in _FACTUAL_FIELDS if name not in resolved_factual_fields)
        response_model = _build_response_model(unresolved_factual_fields)
        is_fast_path = not unresolved_factual_fields

        prompt_hints = _build_prompt_hints(candidates)
        requested_fields = unresolved_factual_fields + ("business_name", "category")

        # Send exactly one image, never both a full original and an enhanced
        # copy: the cropped/enhanced variant when document cropping was
        # confident (it is a closer, cleaner view of just the receipt), the
        # original photo only as a fallback when cropping was not confident
        # (e.g. no clear document boundary was found at all).
        if ocr_result.vision_image is not None:
            buffer = io.BytesIO()
            ocr_result.vision_image.convert("RGB").save(buffer, format="PNG")
            images_b64 = [b64encode(buffer.getvalue()).decode("ascii")]
        else:
            images_b64 = [b64encode(path.read_bytes()).decode("ascii")]

        num_ctx = self._settings.ollama_num_ctx_fast if is_fast_path else self._settings.ollama_num_ctx
        num_predict = self._settings.ollama_num_predict_fast if is_fast_path else self._settings.ollama_num_predict

        payload = {
            "model": self._settings.ollama_receipt_model,
            "prompt": build_ocr_assisted_prompt(ocr_result.summary_text, prompt_hints, requested_fields=requested_fields),
            "images": images_b64,
            "stream": False,
            "format": response_model.model_json_schema(),
            "options": {
                # Explicit, not left at the model's own Ollama default: the
                # image plus the full instruction/OCR-hint prompt can exceed a
                # small default context window outright (observed: a 400
                # "exceeds context size" error, not a graceful degradation) on
                # at least one supported model. The smaller "_fast" budgets
                # are used only once every factual field is already resolved,
                # since the response schema itself is then much smaller too.
                "num_ctx": num_ctx,
                "num_predict": num_predict,
                # Deterministic sampling: temperature=0 plus a fixed seed make
                # the model's own output reproducible run-to-run on the same
                # input, instead of varying with each call as observed before
                # this was set explicitly (see README "Local model choice").
                "temperature": self._settings.ollama_temperature,
                "seed": self._settings.ollama_seed,
            },
        }

        try:
            raw = self._generate_with_retries(client, payload, response_model)
        except ReceiptExtractionParsingError:
            if not is_fast_path:
                raise
            # The reduced "_fast" schema/budget was measured safe and
            # reliably fast for at least one supported model (see README
            # "Local model choice"), but a "thinking"-style model's reasoning
            # overhead does not necessarily shrink just because the requested
            # schema did — observed for real to still truncate the reduced
            # schema's response even at the full num_predict budget. Rather
            # than fail the whole extraction outright, retry once with the
            # SAME full schema/budget combination already validated to work
            # reliably for that case (asking about every field again, not
            # just the previously-unresolved ones). This is still safe for
            # the parser's high-confidence fields: merge_field's precedence
            # rules mean a parser-resolved field can never actually be
            # overwritten by whatever the model says here, widening the
            # schema back out only gives the model more room to finish its
            # own reasoning, never a route to override deterministic values.
            response_model = _build_response_model(_FACTUAL_FIELDS)
            payload["format"] = response_model.model_json_schema()
            payload["prompt"] = build_ocr_assisted_prompt(
                ocr_result.summary_text, prompt_hints, requested_fields=_FACTUAL_FIELDS + ("business_name", "category")
            )
            payload["options"]["num_ctx"] = self._settings.ollama_num_ctx
            payload["options"]["num_predict"] = self._settings.ollama_num_predict
            raw = self._generate_with_retries(client, payload, response_model)

        raw_business_name = getattr(raw, "business_name", None)
        raw_receipt_number = getattr(raw, "receipt_number", None)
        raw_date = getattr(raw, "date", None)
        raw_total = getattr(raw, "total", None)
        raw_vat = getattr(raw, "vat", None)
        raw_currency = getattr(raw, "currency", None)
        raw_category = getattr(raw, "category", ExpenseCategory.OTHER.value)
        raw_warnings = list(getattr(raw, "warnings", []))

        extra_warnings = raw_warnings
        if ocr_result.warning:
            extra_warnings.append(ocr_result.warning)
        category = self._coerce_category(raw_category, extra_warnings)

        model_date, date_warning = _parse_iso_date(raw_date)
        if date_warning:
            extra_warnings.append(date_warning)

        merged = merge_receipt_fields(
            business_name=raw_business_name,
            receipt_number=raw_receipt_number,
            date=model_date,
            total=to_decimal(raw_total),
            vat=to_decimal(raw_vat),
            currency=raw_currency,
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

        if category == ExpenseCategory.OTHER:
            # The vision model itself had nothing better than "other" — try a
            # conservative, generic merchant-name keyword fallback before
            # giving up. Never overrides a category the model was confident
            # about, and never invents one when the merchant name itself is
            # unknown or unrecognized.
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
    def _coerce_category(raw_category: str, warnings: list[str]) -> ExpenseCategory:
        try:
            return ExpenseCategory(raw_category)
        except ValueError:
            if "category_not_confident" not in warnings:
                warnings.append("category_not_confident")
            return ExpenseCategory.OTHER

    def _generate_with_retries(self, client: httpx.Client, payload: dict, response_model: type[BaseModel]) -> BaseModel:
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

        # Some models (observed: qwen3-vl) route structured-output content
        # through Ollama's "thinking" field instead of "response" even when a
        # JSON `format` schema was requested — falling back to it here is a
        # general robustness fix, not specific to one model, since either
        # field is a legitimate place a compliant Ollama response could put
        # the actual answer.
        raw_text = body.get("response") or body.get("thinking")
        if not raw_text:
            raise ReceiptExtractionParsingError("The local model returned no structured output.")

        try:
            return response_model.model_validate_json(raw_text)
        except ValidationError as exc:
            raise ReceiptExtractionParsingError("Could not parse the local model's structured output.") from exc

    def _backoff_seconds(self, attempt: int) -> float:
        return min(self._retry_backoff_base_seconds * (2**attempt), 5)

    def _run_ocr(self, path: Path) -> _OcrExtractionResult:
        if pytesseract is None:
            return _OcrExtractionResult(warning="ocr_unavailable")
        try:
            with Image.open(path) as image:
                variants, detection = generate_variants_with_detection(image)
                candidates = run_ocr_candidates(variants, self._settings.tesseract_languages)
                # Only used as the vision-model image when cropping was
                # confident (detection.cropped) — a wrong/no crop must never
                # be sent in place of the original photo. image closes on
                # exit, so copy() before it does.
                vision_image = variants["enhanced"].copy() if detection.cropped else None
            if not candidates:
                return _OcrExtractionResult(detection=detection, vision_image=vision_image, warning="ocr_unavailable")
            ranked = sorted(candidates, key=lambda c: -c.score)
            ranked_lines = [c.lines for c in ranked]
            summary = build_ocr_summary(ranked[0].lines)
            return _OcrExtractionResult(
                summary_text=summary, ranked_lines=ranked_lines, detection=detection, vision_image=vision_image
            )
        except Exception:  # noqa: BLE001 - OCR is best-effort; any failure falls back to image-only
            logger.info("receipt_ocr result=failure")  # safe: no text/image content logged
            return _OcrExtractionResult(warning="ocr_unavailable")
