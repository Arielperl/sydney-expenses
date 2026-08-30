"""Runs Tesseract across a small, bounded set of (preprocessing variant, page
segmentation mode) combinations and picks the best-scoring result, instead of
trusting a single OCR pass blindly.

The scoring heuristic is deliberately simple and documented as a heuristic,
not a calibrated measure of OCR accuracy: it rewards recognizable receipt
structure (known Hebrew label keywords, money-shaped number patterns) and
penalizes near-empty or garbage-heavy output. Only the single winning text is
ever returned — candidates are never concatenated together, so the model
prompt never sees the same receipt lines repeated several times over.
"""

import re
from dataclasses import dataclass

from PIL import Image

try:
    import pytesseract
except ImportError:  # pragma: no cover - pytesseract is a declared dependency
    pytesseract = None  # type: ignore[assignment]

from app.services.extraction.image_preprocessing import generate_variants

# Bounded: at most len(CANDIDATE_CONFIGS) Tesseract calls per extraction, so
# runtime/memory stay predictable regardless of image content.
CANDIDATE_CONFIGS: tuple[tuple[str, str], ...] = (
    ("enhanced", "6"),  # a single uniform block of text — the common case
    ("enhanced", "4"),  # a single column of variable-sized text
    ("enhanced", "11"),  # sparse text, no particular layout
    ("threshold", "6"),
    ("denoised", "6"),
)

_MONEY_PATTERN = re.compile(r"\d{1,3}[.,]\d{2}\b")
_KEYWORDS = (
    'סה"כ',
    "סהכ",
    "לתשלום",
    "שולם",
    'מע"מ',
    "מעמ",
    "עודף",
    "תאריך",
    "קבלה",
    "מזומן",
    "אשראי",
    "total",
    "vat",
)


@dataclass(frozen=True)
class OcrCandidate:
    variant: str
    psm: str
    text: str
    score: float


def score_ocr_text(text: str) -> float:
    """Heuristic only: rewards receipt-shaped structure, penalizes near-empty
    or noise-only output. Not a measure of transcription accuracy."""
    stripped = text.strip()
    if not stripped:
        return 0.0

    lower = stripped.lower()
    keyword_hits = sum(1 for kw in _KEYWORDS if kw.lower() in lower)
    money_hits = len(_MONEY_PATTERN.findall(stripped))

    recognizable_chars = sum(
        1
        for ch in stripped
        if ch.isalnum() or ch in " \n.,:%-/"
    )
    noise_ratio = 1 - (recognizable_chars / len(stripped))

    length_score = min(len(stripped) / 200, 1.0)

    score = keyword_hits * 3 + money_hits * 2 + length_score - noise_ratio * 5
    return round(score, 3)


def run_ocr_candidates(variants: dict[str, Image.Image], languages: str) -> list[OcrCandidate]:
    """Runs the bounded (variant, psm) matrix against already-generated
    preprocessing variants (see image_preprocessing.generate_variants) and
    returns every candidate tried, each with its heuristic score."""
    if pytesseract is None:
        return []

    candidates: list[OcrCandidate] = []
    for variant_name, psm in CANDIDATE_CONFIGS:
        variant_image = variants.get(variant_name)
        if variant_image is None:
            continue
        try:
            text = pytesseract.image_to_string(
                variant_image, lang=languages, config=f"--psm {psm}"
            )
        except Exception:  # noqa: BLE001 - one bad config must not abort the others
            continue
        candidates.append(OcrCandidate(variant_name, psm, text, score_ocr_text(text)))

    return candidates


def select_best_ocr_text(image: Image.Image, languages: str) -> tuple[str, list[OcrCandidate]]:
    """Convenience entry point that generates the variants itself. Returns the
    best-scoring text plus every candidate tried (for tests/diagnostics only —
    never logged or returned from the API, since it contains raw receipt
    text)."""
    if pytesseract is None:
        return "", []

    variants = generate_variants(image)
    candidates = run_ocr_candidates(variants, languages)
    if not candidates:
        return "", []

    best = max(candidates, key=lambda c: c.score)
    return best.text.strip(), candidates
