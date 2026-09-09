from PIL import Image

from app.services.extraction.image_preprocessing import generate_variants
from app.services.extraction.ocr_selection import (
    CANDIDATE_CONFIGS,
    OcrLine,
    OcrWord,
    build_ocr_summary,
    run_ocr_candidates,
    score_ocr_text,
    select_best_ocr_candidate,
)


def _line(text: str, top: int) -> OcrLine:
    words = tuple(OcrWord(text=t, left=i * 20, top=top, width=15, height=20, conf=90.0) for i, t in enumerate(text.split(" ")))
    return OcrLine(words=words, text=text, top=top, bottom=top + 20, left=0, right=200)


def _fake_image_to_data(lines: list[list[str]]) -> dict:
    """Builds a fake pytesseract.image_to_data()-shaped DICT output from a
    list of lines, each a list of word tokens — a reasonable synthetic stand-in
    for real OCR word boxes, sufficient for testing the bounded-matrix and
    scoring logic without needing real image data."""
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
    top = 0
    for line_idx, words in enumerate(lines):
        left = 0
        for word_idx, token in enumerate(words):
            data["level"].append(5)
            data["block_num"].append(1)
            data["par_num"].append(1)
            data["line_num"].append(line_idx)
            data["word_num"].append(word_idx)
            data["left"].append(left)
            data["top"].append(top)
            data["width"].append(len(token) * 12 + 8)
            data["height"].append(28)
            data["conf"].append(90.0)
            data["text"].append(token)
            left += len(token) * 12 + 20
        top += 40
    return data


class _FakePytesseract:
    """Returns a different, deterministic fake word-data response per (psm)
    so tests can verify the bounded matrix is actually being exercised and
    that scoring picks the best-shaped one."""

    call_log: list[tuple[str, str]] = []

    @classmethod
    def image_to_data(cls, image, lang=None, config=None, output_type=None):
        psm = config.split()[-1] if config else "?"
        cls.call_log.append((lang, psm))
        if psm == "6":
            return _fake_image_to_data([['סה"כ', "לתשלום", "45.00"], ['מע"מ', "6.50"]])
        return _fake_image_to_data([["garbled", "!@#"]])

    class Output:
        DICT = "dict"


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


def test_run_ocr_candidates_reconstructs_spatial_lines(monkeypatch):
    import app.services.extraction.ocr_selection as ocr_selection_module

    _FakePytesseract.call_log = []
    monkeypatch.setattr(ocr_selection_module, "pytesseract", _FakePytesseract)

    image = Image.new("L", (330, 736), color=255)
    variants = generate_variants(image)
    candidates = run_ocr_candidates(variants, "heb+eng")

    best = max(candidates, key=lambda c: c.score)
    assert len(best.lines) == 2
    assert best.lines[0].text == 'סה"כ לתשלום 45.00'
    assert best.lines[1].text == 'מע"מ 6.50'
    assert best.lines[1].top > best.lines[0].top


def test_select_best_ocr_candidate_picks_the_highest_scoring_one(monkeypatch):
    import app.services.extraction.ocr_selection as ocr_selection_module

    _FakePytesseract.call_log = []
    monkeypatch.setattr(ocr_selection_module, "pytesseract", _FakePytesseract)

    image = Image.new("L", (330, 736), color=255)
    best, candidates = select_best_ocr_candidate(image, "heb+eng")

    assert best is not None
    assert "לתשלום" in best.text
    assert len(candidates) == len(CANDIDATE_CONFIGS)


def test_a_single_bad_config_does_not_abort_the_others(monkeypatch):
    import app.services.extraction.ocr_selection as ocr_selection_module

    class _PartiallyFailingPytesseract:
        @staticmethod
        def image_to_data(image, lang=None, config=None, output_type=None):
            if config and config.endswith("4"):
                raise RuntimeError("simulated tesseract failure for this config")
            return _fake_image_to_data([['סה"כ', "לתשלום", "20.00"]])

        class Output:
            DICT = "dict"

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
    best, candidates = select_best_ocr_candidate(image, "heb+eng")
    assert best is None
    assert candidates == []


# --- build_ocr_summary --------------------------------------------------


def test_build_ocr_summary_keeps_header_and_labeled_lines():
    lines = tuple(
        _line(text, top=i * 30)
        for i, text in enumerate(
            [
                "פלסטלינה",
                "רחוב הרצל 10",
                "פריט א 10.00",
                "פריט ב 20.00",
                'סה"כ לתשלום 30.00',
            ]
        )
    )
    summary = build_ocr_summary(lines, header_lines=2, max_item_lines=0)
    assert "פלסטלינה" in summary
    assert "רחוב הרצל 10" in summary
    assert 'סה"כ לתשלום 30.00' in summary
    # A plain, unlabeled item line beyond the header is dropped when the
    # item budget is exhausted (max_item_lines=0 above).
    assert "פריט א 10.00" not in summary


def test_build_ocr_summary_never_drops_a_labeled_line_regardless_of_position():
    """A keyword/labeled line far down a long receipt must survive even when
    it would otherwise fall outside the header and the item-line budget."""
    item_lines = [f"פריט {i} {i}.00" for i in range(30)]
    lines = tuple(_line(text, top=i * 30) for i, text in enumerate(["חנות", *item_lines, 'סה"כ לתשלום 99.00']))
    summary = build_ocr_summary(lines, header_lines=1, max_item_lines=5)
    assert 'סה"כ לתשלום 99.00' in summary


def test_build_ocr_summary_preserves_original_top_to_bottom_order():
    lines = tuple(_line(text, top=i * 30) for i, text in enumerate(["חנות", 'סה"כ לתשלום 10.00', "תודה"]))
    summary = build_ocr_summary(lines, header_lines=1, max_item_lines=5)
    assert summary.splitlines() == ["חנות", 'סה"כ לתשלום 10.00', "תודה"]


def test_build_ocr_summary_empty_lines_returns_empty_string():
    assert build_ocr_summary(()) == ""
