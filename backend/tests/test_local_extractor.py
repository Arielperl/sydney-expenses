import json
from decimal import Decimal

import httpx
import pytest

from app.api.deps import get_receipt_extractor
from app.core.config import get_settings
from app.services.extraction.document_geometry import DocumentDetection
from app.services.extraction.exceptions import (
    ReceiptExtractionParsingError,
    ReceiptExtractionProviderError,
    ReceiptExtractionTimeoutError,
)
from app.services.extraction.local_extractor import LocalReceiptExtractor, _OcrExtractionResult
from app.services.extraction.mock import MockReceiptExtractor


def _fake_image_to_data(text: str) -> dict:
    """Builds a fake pytesseract.image_to_data()-shaped DICT output from a
    plain multi-line string, splitting each line into words (increasing left
    position per word) — a reasonable synthetic stand-in for real OCR word
    boxes, sufficient for these end-to-end prompt/logging tests."""
    data: dict[str, list] = {
        "level": [],
        "block_num": [],
        "par_num": [],
        "line_num": [],
        "word_num": [],
        "left": [],
        "top": [],
        "width": [],
        "height": [],
        "conf": [],
        "text": [],
    }
    for line_idx, line in enumerate(text.splitlines()):
        if not line.strip():
            continue
        left = 0
        for word_idx, token in enumerate(line.split(" ")):
            if not token:
                continue
            width = len(token) * 10 + 8
            data["level"].append(5)
            data["block_num"].append(1)
            data["par_num"].append(1)
            data["line_num"].append(line_idx)
            data["word_num"].append(word_idx)
            data["left"].append(left)
            data["top"].append(line_idx * 40)
            data["width"].append(width)
            data["height"].append(28)
            data["conf"].append(90.0)
            data["text"].append(token)
            left += width + 15
    return data


class _FakeOutputEnum:
    DICT = "dict"


def _raw_json(**overrides) -> str:
    defaults = dict(
        business_name="Shufersal",
        receipt_number="12345",
        date="2026-01-15",
        total=184.90,
        vat=26.65,
        currency="ILS",
        category="groceries",
        warnings=[],
    )
    defaults.update(overrides)
    return json.dumps(defaults)


class _FakeResponse:
    def __init__(self, json_body=None, status_code=200, raw_text: str | None = None, thinking: str | None = None):
        self._json_body = json_body
        self.status_code = status_code
        self._raw_text = raw_text
        self._thinking = thinking

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("POST", "http://localhost:11434/api/generate")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("error", request=request, response=response)

    def json(self):
        if self._thinking is not None:
            return {"response": self._raw_text or "", "thinking": self._thinking}
        if self._raw_text is not None:
            return {"response": self._raw_text}
        if self._json_body is None:
            raise ValueError("no body")
        return {"response": self._json_body}


class _FakeHttpClient:
    """Stands in for httpx.Client. `behaviors` is a queue of either a _FakeResponse
    to return or an exception instance to raise — consumed one per call."""

    def __init__(self, behaviors):
        self._behaviors = list(behaviors)
        self.call_count = 0
        self.last_payload = None
        self.payloads: list[dict] = []

    def post(self, url, json=None):
        # Snapshot, not a bare reference: real httpx serializes the payload
        # to bytes on the wire immediately, so a caller mutating its own
        # `payload` dict afterward (e.g. to retry with different options)
        # must never retroactively change what an earlier call is recorded
        # as having actually sent.
        import copy as _copy

        self.call_count += 1
        snapshot = _copy.deepcopy(json)
        self.last_payload = snapshot
        self.payloads.append(snapshot)
        behavior = self._behaviors.pop(0)
        if isinstance(behavior, BaseException):
            raise behavior
        return behavior


def _settings_with_local(**overrides):
    settings = get_settings().model_copy(
        update={
            "receipt_extractor_provider": "local",
            "ollama_max_retries": 2,
            **overrides,
        }
    )
    return settings


def _dummy_image(tmp_path):
    path = tmp_path / "receipt.png"
    path.write_bytes(b"fake-bytes")
    return str(path)


def _valid_image(tmp_path):
    from tests.conftest import VALID_PNG_BYTES

    path = tmp_path / "receipt.png"
    path.write_bytes(VALID_PNG_BYTES)
    return str(path)


def _extractor_with_no_ocr(settings, client):
    extractor = LocalReceiptExtractor(settings, http_client=client)
    extractor._run_ocr = lambda path: _OcrExtractionResult()  # bypass real Tesseract in unit tests
    return extractor


# --- Provider selection ---------------------------------------------------


def test_default_provider_is_mock():
    get_settings.cache_clear()
    get_receipt_extractor.cache_clear()
    try:
        assert isinstance(get_receipt_extractor(), MockReceiptExtractor)
    finally:
        get_settings.cache_clear()
        get_receipt_extractor.cache_clear()


def test_local_provider_selected_with_valid_config(monkeypatch):
    monkeypatch.setenv("RECEIPT_EXTRACTOR_PROVIDER", "local")
    get_settings.cache_clear()
    get_receipt_extractor.cache_clear()
    try:
        assert isinstance(get_receipt_extractor(), LocalReceiptExtractor)
    finally:
        get_settings.cache_clear()
        get_receipt_extractor.cache_clear()


# --- Mapping a valid response ------------------------------------------------


def test_maps_a_valid_structured_response(tmp_path):
    client = _FakeHttpClient([_FakeResponse(json_body=_raw_json())])
    extractor = _extractor_with_no_ocr(_settings_with_local(), client)

    result = extractor.extract(_dummy_image(tmp_path))

    assert result.business_name == "Shufersal"
    assert result.total == Decimal("184.90")
    assert result.vat == Decimal("26.65")
    assert result.currency == "ILS"
    assert result.category == "groceries"
    assert 0 <= result.confidence <= 1


def test_uses_json_schema_format_and_includes_image(tmp_path):
    client = _FakeHttpClient([_FakeResponse(json_body=_raw_json())])
    settings = _settings_with_local(ollama_receipt_model="gemma3:12b")
    extractor = _extractor_with_no_ocr(settings, client)

    extractor.extract(_dummy_image(tmp_path))

    payload = client.last_payload
    assert payload["model"] == "gemma3:12b"
    assert payload["stream"] is False
    assert "properties" in payload["format"]  # a real JSON schema, not free-form
    assert len(payload["images"]) == 1
    assert payload["options"]["num_ctx"] > 0


def test_num_ctx_is_configurable_and_sent_explicitly(tmp_path):
    client = _FakeHttpClient([_FakeResponse(json_body=_raw_json())])
    extractor = _extractor_with_no_ocr(_settings_with_local(ollama_num_ctx=16384), client)

    extractor.extract(_dummy_image(tmp_path))

    assert client.last_payload["options"]["num_ctx"] == 16384


def test_currency_is_normalized_to_uppercase(tmp_path):
    client = _FakeHttpClient([_FakeResponse(json_body=_raw_json(currency="ils"))])
    extractor = _extractor_with_no_ocr(_settings_with_local(), client)
    result = extractor.extract(_dummy_image(tmp_path))
    assert result.currency == "ILS"


# --- Nullable / partial / invalid fields -------------------------------------


def test_nullable_optional_fields_are_handled(tmp_path):
    client = _FakeHttpClient(
        [_FakeResponse(json_body=_raw_json(business_name=None, receipt_number=None, date=None, total=None, vat=None))]
    )
    extractor = _extractor_with_no_ocr(_settings_with_local(), client)

    result = extractor.extract(_dummy_image(tmp_path))

    assert result.business_name is None
    assert result.total is None
    assert "business_name_not_confident" in result.warnings
    assert "total_not_confident" in result.warnings


def test_invalid_date_is_discarded_with_warning(tmp_path):
    client = _FakeHttpClient([_FakeResponse(json_body=_raw_json(date="not-a-date"))])
    extractor = _extractor_with_no_ocr(_settings_with_local(), client)
    result = extractor.extract(_dummy_image(tmp_path))
    assert result.date is None
    assert "date_not_confident" in result.warnings


def test_vat_greater_than_total_is_discarded(tmp_path):
    client = _FakeHttpClient([_FakeResponse(json_body=_raw_json(total=10.0, vat=50.0))])
    extractor = _extractor_with_no_ocr(_settings_with_local(), client)
    result = extractor.extract(_dummy_image(tmp_path))
    assert result.vat is None
    assert "vat_amount_not_confident" in result.warnings


def test_invalid_currency_falls_back_to_ils(tmp_path):
    client = _FakeHttpClient([_FakeResponse(json_body=_raw_json(currency="1LS"))])
    extractor = _extractor_with_no_ocr(_settings_with_local(), client)
    result = extractor.extract(_dummy_image(tmp_path))
    assert result.currency == "ILS"


def test_invalid_category_falls_back_to_other(tmp_path):
    client = _FakeHttpClient([_FakeResponse(json_body=_raw_json(category="not-a-real-category"))])
    extractor = _extractor_with_no_ocr(_settings_with_local(), client)
    result = extractor.extract(_dummy_image(tmp_path))
    assert result.category == "other"


def test_malformed_json_output_raises_parsing_error(tmp_path):
    client = _FakeHttpClient([_FakeResponse(raw_text="this is not json")])
    extractor = _extractor_with_no_ocr(_settings_with_local(), client)
    with pytest.raises(ReceiptExtractionParsingError):
        extractor.extract(_dummy_image(tmp_path))


def test_empty_response_raises_parsing_error(tmp_path):
    client = _FakeHttpClient([_FakeResponse(raw_text="")])
    extractor = _extractor_with_no_ocr(_settings_with_local(), client)
    with pytest.raises(ReceiptExtractionParsingError):
        extractor.extract(_dummy_image(tmp_path))


def test_falls_back_to_thinking_field_when_response_is_empty(tmp_path):
    """Some models (observed: qwen3-vl) route the structured JSON output
    through Ollama's "thinking" field instead of "response" even with a JSON
    `format` schema requested — this must not be treated as no output at all."""
    client = _FakeHttpClient([_FakeResponse(thinking=_raw_json(total=42.5))])
    extractor = _extractor_with_no_ocr(_settings_with_local(), client)
    result = extractor.extract(_dummy_image(tmp_path))
    assert result.total == Decimal("42.50")


def test_num_predict_is_sent_explicitly(tmp_path):
    client = _FakeHttpClient([_FakeResponse(json_body=_raw_json())])
    extractor = _extractor_with_no_ocr(_settings_with_local(ollama_num_predict=4096), client)
    extractor.extract(_dummy_image(tmp_path))
    assert client.last_payload["options"]["num_predict"] == 4096


# --- Ollama availability / timeout / retries ---------------------------------


def test_ollama_unavailable_raises_clear_provider_error(tmp_path, monkeypatch):
    monkeypatch.setattr(LocalReceiptExtractor, "_retry_backoff_base_seconds", 0)
    connect_error = httpx.ConnectError("Connection refused")
    client = _FakeHttpClient([connect_error, connect_error, connect_error])
    extractor = _extractor_with_no_ocr(_settings_with_local(ollama_max_retries=2), client)

    with pytest.raises(ReceiptExtractionProviderError, match="Ollama"):
        extractor.extract(_dummy_image(tmp_path))

    assert client.call_count == 3  # initial attempt + 2 retries


def test_timeout_retries_then_raises_after_bound_exhausted(tmp_path, monkeypatch):
    monkeypatch.setattr(LocalReceiptExtractor, "_retry_backoff_base_seconds", 0)
    timeout = httpx.TimeoutException("timed out")
    client = _FakeHttpClient([timeout, timeout, timeout])
    extractor = _extractor_with_no_ocr(_settings_with_local(ollama_max_retries=2), client)

    with pytest.raises(ReceiptExtractionTimeoutError):
        extractor.extract(_dummy_image(tmp_path))

    assert client.call_count == 3


def test_transient_5xx_retries_then_succeeds(tmp_path, monkeypatch):
    monkeypatch.setattr(LocalReceiptExtractor, "_retry_backoff_base_seconds", 0)
    client = _FakeHttpClient(
        [_FakeResponse(status_code=503), _FakeResponse(status_code=503), _FakeResponse(json_body=_raw_json())]
    )
    extractor = _extractor_with_no_ocr(_settings_with_local(ollama_max_retries=2), client)

    result = extractor.extract(_dummy_image(tmp_path))

    assert result.business_name == "Shufersal"
    assert client.call_count == 3


def test_non_transient_error_is_not_retried(tmp_path):
    client = _FakeHttpClient([_FakeResponse(status_code=400)])
    extractor = _extractor_with_no_ocr(_settings_with_local(ollama_max_retries=2), client)

    with pytest.raises(ReceiptExtractionProviderError):
        extractor.extract(_dummy_image(tmp_path))

    assert client.call_count == 1


# --- OCR: Hebrew/English handling and Tesseract-failure fallback ------------


def test_hebrew_and_english_ocr_text_is_included_in_the_prompt(tmp_path, monkeypatch):
    import app.services.extraction.ocr_selection as ocr_selection_module

    class _FakePytesseract:
        @staticmethod
        def image_to_data(image, lang=None, config=None, output_type=None):
            assert lang == "heb+eng"
            return _fake_image_to_data("שופרסל\nTOTAL: 42.50")

        Output = _FakeOutputEnum

    monkeypatch.setattr(ocr_selection_module, "pytesseract", _FakePytesseract)

    client = _FakeHttpClient([_FakeResponse(json_body=_raw_json())])
    extractor = LocalReceiptExtractor(_settings_with_local(), http_client=client)

    extractor.extract(_valid_image(tmp_path))

    assert "שופרסל" in client.last_payload["prompt"]
    assert "TOTAL: 42.50" in client.last_payload["prompt"]


def test_tesseract_failure_falls_back_to_image_only_extraction(tmp_path, monkeypatch):
    import app.services.extraction.ocr_selection as ocr_selection_module

    class _FailingPytesseract:
        @staticmethod
        def image_to_data(image, lang=None, config=None, output_type=None):
            raise RuntimeError("tesseract binary not found")

        Output = _FakeOutputEnum

    monkeypatch.setattr(ocr_selection_module, "pytesseract", _FailingPytesseract)

    client = _FakeHttpClient([_FakeResponse(json_body=_raw_json())])
    extractor = LocalReceiptExtractor(_settings_with_local(), http_client=client)

    result = extractor.extract(_valid_image(tmp_path))

    assert result.business_name == "Shufersal"  # extraction still succeeded via the image
    assert "ocr_unavailable" in result.warnings


def test_sensitive_ocr_content_is_not_logged(tmp_path, monkeypatch, caplog):
    import app.services.extraction.ocr_selection as ocr_selection_module

    secret_text = "שם פרטי: ישראל ישראלי מספר כרטיס 4111111111111111"

    class _FakePytesseract:
        @staticmethod
        def image_to_data(image, lang=None, config=None, output_type=None):
            raise RuntimeError(secret_text)  # simulate an error that could embed OCR text

        Output = _FakeOutputEnum

    monkeypatch.setattr(ocr_selection_module, "pytesseract", _FakePytesseract)

    client = _FakeHttpClient([_FakeResponse(json_body=_raw_json())])
    extractor = LocalReceiptExtractor(_settings_with_local(), http_client=client)

    with caplog.at_level("DEBUG"):
        extractor.extract(_valid_image(tmp_path))

    for record in caplog.records:
        assert secret_text not in record.getMessage()
        assert "fake-bytes" not in record.getMessage()  # the raw image bytes


# --- Upload-route level: extraction failure must not block manual entry -----


def test_upload_with_ollama_unreachable_still_saves_the_file_and_allows_manual_entry(client, monkeypatch):
    import io

    from app.api.deps import get_receipt_extractor as _get_receipt_extractor
    from tests.conftest import VALID_PNG_BYTES

    monkeypatch.setenv("RECEIPT_EXTRACTOR_PROVIDER", "local")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:1")  # nothing listens here
    monkeypatch.setenv("OLLAMA_MAX_RETRIES", "0")
    get_settings.cache_clear()
    _get_receipt_extractor.cache_clear()
    try:
        response = client.post(
            "/api/receipts/upload",
            files={"file": ("receipt.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["extraction_succeeded"] is False
        assert body["receipt_image_url"].startswith("/uploads/")

        confirm_response = client.post(
            "/api/receipts/confirm",
            json={
                "upload_id": body["upload_id"],
                "business_name": "Manual Entry",
                "amount": 10,
                "currency": "ILS",
                "category": "other",
                "expense_date": "2026-01-01",
            },
        )
        assert confirm_response.status_code == 201
    finally:
        monkeypatch.setenv("RECEIPT_EXTRACTOR_PROVIDER", "mock")
        get_settings.cache_clear()
        _get_receipt_extractor.cache_clear()


def test_no_expense_saved_during_local_extraction_itself(client, monkeypatch):
    import io

    from app.api.deps import get_receipt_extractor as _get_receipt_extractor
    from tests.conftest import VALID_PNG_BYTES

    monkeypatch.setenv("RECEIPT_EXTRACTOR_PROVIDER", "local")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:1")
    monkeypatch.setenv("OLLAMA_MAX_RETRIES", "0")
    get_settings.cache_clear()
    _get_receipt_extractor.cache_clear()
    try:
        client.post(
            "/api/receipts/upload",
            files={"file": ("receipt.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
        )
        assert client.get("/api/expenses").json() == []
    finally:
        monkeypatch.setenv("RECEIPT_EXTRACTOR_PROVIDER", "mock")
        get_settings.cache_clear()
        _get_receipt_extractor.cache_clear()


# --- /system/capabilities for local mode -------------------------------------


def test_system_capabilities_reports_local_mode(client, monkeypatch):
    monkeypatch.setenv("RECEIPT_EXTRACTOR_PROVIDER", "local")
    get_settings.cache_clear()
    try:
        response = client.get("/api/system/capabilities")
        body = response.json()
        assert body["receipt_extraction_provider"] == "local"
        assert body["receipt_extraction_mode"] == "local"
        assert body["real_ai_enabled"] is True
        assert isinstance(body["tesseract_available"], bool)
        assert isinstance(body["ollama_available"], bool)
        assert "key" not in str(body).lower()
    finally:
        get_settings.cache_clear()


# --- Deterministic parser + merge, end-to-end through the real extractor ----


def test_parser_recovers_a_value_the_model_missed(tmp_path, monkeypatch):
    """End-to-end: the model returns total=null, but a deterministic label
    match in the OCR text recovers it, and the prompt itself carries that
    candidate as a hint for the model to verify."""
    import app.services.extraction.ocr_selection as ocr_selection_module

    class _FakePytesseract:
        @staticmethod
        def image_to_data(image, lang=None, config=None, output_type=None):
            return _fake_image_to_data('סה"כ לתשלום 60.50\nתאריך: 30/09/2013')

        Output = _FakeOutputEnum

    monkeypatch.setattr(ocr_selection_module, "pytesseract", _FakePytesseract)

    client = _FakeHttpClient([_FakeResponse(json_body=_raw_json(total=None, date=None, vat=None))])
    extractor = LocalReceiptExtractor(_settings_with_local(), http_client=client)

    result = extractor.extract(_valid_image(tmp_path))

    assert result.total == Decimal("60.50")
    assert result.date == __import__("datetime").date(2013, 9, 30)
    assert "total_from_ocr" in result.warnings
    assert "date_from_ocr" in result.warnings
    # The stale "not confident" warning must not survive alongside a value
    # that was, in fact, successfully recovered.
    assert "total_not_confident" not in result.warnings
    assert "date_not_confident" not in result.warnings

    prompt = client.last_payload["prompt"]
    assert "deterministic text-pattern pass" in prompt
    assert "60.5" in prompt


def test_conflicting_model_and_medium_confidence_parser_value_lets_model_win(tmp_path, monkeypatch):
    """A weakly-labeled (medium-confidence) parser match is still asked of
    the model (unlike a high-confidence one — see the exclusion test below),
    and when the two disagree the model's value wins, but the disagreement
    is still surfaced as a warning rather than resolved silently."""
    import app.services.extraction.ocr_selection as ocr_selection_module

    calls = {"n": 0}

    class _FakePytesseract:
        @staticmethod
        def image_to_data(image, lang=None, config=None, output_type=None):
            # Only the first of the several bounded (variant, psm) attempts
            # finds this weak-labeled total; the rest see nothing — this
            # keeps the field at a genuine single-attempt "medium" confidence
            # instead of being cross-attempt-upgraded to "high" by trivially
            # agreeing with itself across every attempt (see
            # parse_receipt_candidates' cross-validation).
            calls["n"] += 1
            return _fake_image_to_data('סה"כ 60.50' if calls["n"] == 1 else "")

        Output = _FakeOutputEnum

    monkeypatch.setattr(ocr_selection_module, "pytesseract", _FakePytesseract)

    client = _FakeHttpClient([_FakeResponse(json_body=_raw_json(total=999.00))])
    extractor = LocalReceiptExtractor(_settings_with_local(), http_client=client)

    result = extractor.extract(_valid_image(tmp_path))

    assert "total_conflicting_sources" in result.warnings
    assert result.total == Decimal("999.00")


def test_high_confidence_ocr_value_excludes_field_from_model_request_and_cannot_be_overwritten(tmp_path, monkeypatch):
    """When the deterministic parser resolves a factual field with high
    confidence, that field must be dropped from the model's response schema
    entirely — not merely overridden after the fact — so a stochastic model
    answer can never even be offered as a conflicting value for it. Uses
    synthetic values structurally similar to a real receipt this task's
    evaluation was measured against (never the real receipt itself)."""
    import app.services.extraction.ocr_selection as ocr_selection_module

    class _FakePytesseract:
        @staticmethod
        def image_to_data(image, lang=None, config=None, output_type=None):
            return _fake_image_to_data(
                "פלסטלינה\n"
                "חשבונית מס' קבלה 3-379380\n"
                "תאריך: 23/08/2026\n"
                'סה"כ לתשלום 435.90\n'
                'מע"מ 66.49\n'
                "₪"
            )

        Output = _FakeOutputEnum

    monkeypatch.setattr(ocr_selection_module, "pytesseract", _FakePytesseract)

    # The model's own (fake) answer deliberately disagrees with every
    # high-confidence field, to prove those values are structurally ignored.
    client = _FakeHttpClient(
        [
            _FakeResponse(
                json_body=_raw_json(
                    receipt_number="000000",
                    date="2000-01-01",
                    total=1.0,
                    vat=1.0,
                    currency="USD",
                    business_name="Plastelina",
                    category="shopping",
                )
            )
        ]
    )
    extractor = LocalReceiptExtractor(_settings_with_local(), http_client=client)

    result = extractor.extract(_valid_image(tmp_path))

    schema_fields = set(client.last_payload["format"]["properties"])
    assert schema_fields == {"business_name", "category", "warnings"}

    assert result.receipt_number == "3-379380"
    assert result.date == __import__("datetime").date(2026, 8, 23)
    assert result.total == Decimal("435.90")
    assert result.vat == Decimal("66.49")
    assert result.currency == "ILS"

    for code in (
        "receipt_number_conflicting_sources",
        "date_conflicting_sources",
        "total_conflicting_sources",
        "vat_conflicting_sources",
        "currency_conflicting_sources",
    ):
        assert code not in result.warnings
    for code in ("receipt_number_from_ocr", "date_from_ocr", "total_from_ocr", "vat_from_ocr", "currency_from_ocr"):
        assert code in result.warnings

    # The fast num_ctx/num_predict budgets apply once every factual field is
    # resolved, since the response schema is then much smaller too.
    settings = extractor._settings
    assert client.last_payload["options"]["num_ctx"] == settings.ollama_num_ctx_fast
    assert client.last_payload["options"]["num_predict"] == settings.ollama_num_predict_fast


def test_fast_path_falls_back_to_full_schema_and_budget_when_response_fails_to_parse(tmp_path, monkeypatch):
    """A "thinking"-style model's reasoning overhead does not necessarily
    shrink just because the requested schema did — observed for real to
    still truncate a reduced-schema response even at a generous num_predict.
    Rather than fail the whole extraction, a parse failure on the fast path
    is retried once with the full schema/budget combination already
    validated to work reliably (see README "Local model choice")."""
    import app.services.extraction.ocr_selection as ocr_selection_module

    class _FakePytesseract:
        @staticmethod
        def image_to_data(image, lang=None, config=None, output_type=None):
            return _fake_image_to_data(
                "פלסטלינה\n"
                "חשבונית מס' קבלה 3-379380\n"
                "תאריך: 23/08/2026\n"
                'סה"כ לתשלום 435.90\n'
                'מע"מ 66.49\n'
                "₪"
            )

        Output = _FakeOutputEnum

    monkeypatch.setattr(ocr_selection_module, "pytesseract", _FakePytesseract)

    client = _FakeHttpClient(
        [
            _FakeResponse(raw_text='{"business_name": "trunc'),  # fast-path attempt: truncated JSON
            # The retry's own (fake) total (184.90, _raw_json's default) deliberately
            # disagrees with the OCR-resolved 435.90 — proving the wider retry schema
            # still can never let the model override a high-confidence parser value.
            _FakeResponse(json_body=_raw_json(business_name="Plastelina", category="shopping")),
        ]
    )
    extractor = LocalReceiptExtractor(_settings_with_local(), http_client=client)

    result = extractor.extract(_valid_image(tmp_path))

    assert client.call_count == 2
    assert result.category == "shopping"
    # The value itself is protected — the retry's differing (fake) total is
    # never used — but the genuine disagreement is still surfaced, per the
    # "preserve disagreement warnings" merge policy (merge.merge_field).
    assert result.total == Decimal("435.90")
    assert "total_conflicting_sources" in result.warnings

    first_payload, second_payload = client.payloads[0], client.payloads[1]
    settings = extractor._settings
    assert first_payload["options"]["num_ctx"] == settings.ollama_num_ctx_fast
    assert first_payload["options"]["num_predict"] == settings.ollama_num_predict_fast
    assert second_payload["options"]["num_ctx"] == settings.ollama_num_ctx
    assert second_payload["options"]["num_predict"] == settings.ollama_num_predict
    # The retry widens the schema back to every factual field, not just the
    # originally-unresolved ones — the combination already validated safe.
    assert set(first_payload["format"]["properties"]) == {"business_name", "category", "warnings"}
    assert set(second_payload["format"]["properties"]) == {
        "receipt_number",
        "date",
        "total",
        "vat",
        "currency",
        "business_name",
        "category",
        "warnings",
    }


def test_all_null_never_defaults_to_zero_or_today(tmp_path):
    """Nothing resolved by OCR, and the model itself reports every factual
    field as unknown — the result must stay null, never fall back to 0 or
    today's date."""
    client = _FakeHttpClient(
        [_FakeResponse(json_body=_raw_json(receipt_number=None, date=None, total=None, vat=None))]
    )
    extractor = _extractor_with_no_ocr(_settings_with_local(), client)

    result = extractor.extract(_dummy_image(tmp_path))

    assert result.total is None
    assert result.vat is None
    assert result.date is None
    assert result.receipt_number is None


def test_deterministic_sampling_options_are_sent_explicitly(tmp_path):
    client = _FakeHttpClient([_FakeResponse(json_body=_raw_json())])
    extractor = _extractor_with_no_ocr(_settings_with_local(ollama_temperature=0.0, ollama_seed=7), client)

    extractor.extract(_dummy_image(tmp_path))

    assert client.last_payload["options"]["temperature"] == 0.0
    assert client.last_payload["options"]["seed"] == 7


def test_cropped_image_only_is_sent_when_crop_is_confident(tmp_path):
    from PIL import Image

    client = _FakeHttpClient([_FakeResponse(json_body=_raw_json())])
    extractor = LocalReceiptExtractor(_settings_with_local(), http_client=client)
    cropped_image = Image.new("L", (20, 20), color=200)
    extractor._run_ocr = lambda path: _OcrExtractionResult(
        detection=DocumentDetection(cropped=True, confidence=0.5), vision_image=cropped_image
    )

    extractor.extract(_dummy_image(tmp_path))

    assert len(client.last_payload["images"]) == 1
    # Not the raw fake-bytes original — a real (encoded) cropped image instead.
    import base64

    assert base64.b64decode(client.last_payload["images"][0]) != b"fake-bytes"


def test_falls_back_to_original_image_when_crop_is_not_confident(tmp_path):
    client = _FakeHttpClient([_FakeResponse(json_body=_raw_json())])
    extractor = LocalReceiptExtractor(_settings_with_local(), http_client=client)
    extractor._run_ocr = lambda path: _OcrExtractionResult(detection=DocumentDetection(), vision_image=None)

    image_path = _dummy_image(tmp_path)
    extractor.extract(image_path)

    assert len(client.last_payload["images"]) == 1
    import base64

    assert base64.b64decode(client.last_payload["images"][0]) == b"fake-bytes"


def test_full_pipeline_never_logs_ocr_text_or_image_bytes(tmp_path, monkeypatch, caplog):
    import app.services.extraction.ocr_selection as ocr_selection_module

    sensitive_receipt_text = 'שם פרטי: ישראל ישראלי\nסה"כ לתשלום 60.50\nמספר כרטיס 4111111111111111'

    class _FakePytesseract:
        @staticmethod
        def image_to_data(image, lang=None, config=None, output_type=None):
            return _fake_image_to_data(sensitive_receipt_text)

        Output = _FakeOutputEnum

    monkeypatch.setattr(ocr_selection_module, "pytesseract", _FakePytesseract)

    client = _FakeHttpClient([_FakeResponse(json_body=_raw_json())])
    extractor = LocalReceiptExtractor(_settings_with_local(), http_client=client)

    with caplog.at_level("DEBUG"):
        result = extractor.extract(_valid_image(tmp_path))

    assert result.total is not None  # sanity: extraction actually ran
    for record in caplog.records:
        message = record.getMessage()
        assert sensitive_receipt_text not in message
        assert "4111111111111111" not in message
        assert "ישראל ישראלי" not in message
