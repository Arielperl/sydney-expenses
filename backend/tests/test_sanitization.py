from app.services.extraction.sanitization import (
    KNOWN_WARNING_CODES,
    FALLBACK_WARNING_CODE,
    normalize_warnings,
)


def test_known_warning_codes_pass_through_unchanged():
    warnings = ["total_not_confident", "vat_amount_not_confident"]
    assert normalize_warnings(warnings) == warnings


def test_unknown_free_text_warning_is_normalized_to_fallback():
    """A local, quantized model is not as strictly constrained to a fixed
    vocabulary as a hosted strict-structured-output provider — this is the
    real failure mode observed: the model wrote a full English sentence
    (and once even a guessed value) into the warnings field instead of a
    known code. That must never reach the frontend as raw text."""
    warnings = normalize_warnings(["Could not reliably determine merchant name - assuming 'Foo Market'"])
    assert warnings == [FALLBACK_WARNING_CODE]


def test_normalize_warnings_deduplicates_while_preserving_order():
    warnings = normalize_warnings(["total_not_confident", "vat_amount_not_confident", "total_not_confident"])
    assert warnings == ["total_not_confident", "vat_amount_not_confident"]


def test_normalize_warnings_deduplicates_after_fallback_mapping():
    warnings = normalize_warnings(["some free text one", "some free text two"])
    assert warnings == [FALLBACK_WARNING_CODE]


def test_every_known_code_is_a_plausible_snake_case_identifier():
    for code in KNOWN_WARNING_CODES:
        assert code.islower()
        assert " " not in code
