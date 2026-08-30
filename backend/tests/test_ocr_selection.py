from PIL import Image

from app.services.extraction.image_preprocessing import generate_variants
from app.services.extraction.ocr_selection import (
    CANDIDATE_CONFIGS,
    run_ocr_candidates,
    score_ocr_text,
    select_best_ocr_text,
)


class _FakePytesseract:
    """Returns a different, deterministic fake text per (variant, psm) pair
    so tests can verify the bounded matrix is actually being exercised and
    that scoring picks the best-shaped one."""

    call_log: list[tuple[str, str]] = []

    @classmethod
    def image_to_string(cls, image, lang=None, config=None):
        psm = config.split()[-1] if config else "?"
        cls.call_log.append((lang, psm))
        if psm == "6":
            return 'סה"כ לתשלום 45.00\nמע"מ 6.50'  # well-structured, high score
        return "garbled noise !@#"  # low score


def test_score_rewards_receipt_keywords_and_money_patterns():
    good = score_ocr_text('סה"כ לתשלום 45.00 מע"מ 6.50')
    bad = score_ocr_text("asdkjh qweoiu")
    assert good > bad


def test_score_of_empty_text_is_zero():
    assert score_ocr_text("") == 0.0
    assert score_ocr_text("   ") == 0.0


def test_run_ocr_candidates_tries_every_bounded_config_at_most_once(monkeypatch):
    import app.services.extraction.ocr_selection as ocr_selection_module

    _FakePytesseract.call_log = []
    monkeypatch.setattr(ocr_selection_module, "pytesseract", _FakePytesseract)

    image = Image.new("L", (330, 736), color=255)
    variants = generate_variants(image)
    candidates = run_ocr_candidates(variants, "heb+eng")

    assert len(candidates) == len(CANDIDATE_CONFIGS)
    assert len(_FakePytesseract.call_log) == len(CANDIDATE_CONFIGS)


def test_select_best_ocr_text_picks_the_highest_scoring_candidate(monkeypatch):
    import app.services.extraction.ocr_selection as ocr_selection_module

    _FakePytesseract.call_log = []
    monkeypatch.setattr(ocr_selection_module, "pytesseract", _FakePytesseract)

    image = Image.new("L", (330, 736), color=255)
    best_text, candidates = select_best_ocr_text(image, "heb+eng")

    assert "לתשלום" in best_text
    assert len(candidates) == len(CANDIDATE_CONFIGS)


def test_a_single_bad_config_does_not_abort_the_others(monkeypatch):
    import app.services.extraction.ocr_selection as ocr_selection_module

    class _PartiallyFailingPytesseract:
        @staticmethod
        def image_to_string(image, lang=None, config=None):
            if config and config.endswith("4"):
                raise RuntimeError("simulated tesseract failure for this config")
            return 'סה"כ לתשלום 20.00'

    monkeypatch.setattr(ocr_selection_module, "pytesseract", _PartiallyFailingPytesseract)

    image = Image.new("L", (330, 736), color=255)
    variants = generate_variants(image)
    candidates = run_ocr_candidates(variants, "heb+eng")

    assert len(candidates) == len(CANDIDATE_CONFIGS) - 1
    assert all(c.text.strip() for c in candidates)


def test_no_pytesseract_returns_no_candidates(monkeypatch):
    import app.services.extraction.ocr_selection as ocr_selection_module

    monkeypatch.setattr(ocr_selection_module, "pytesseract", None)
    image = Image.new("L", (330, 736), color=255)
    best_text, candidates = select_best_ocr_text(image, "heb+eng")
    assert best_text == ""
    assert candidates == []
