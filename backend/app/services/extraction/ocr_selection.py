"""Runs Tesseract across a small, bounded set of (preprocessing variant, page
segmentation mode) combinations and picks the best-scoring result, instead of
trusting a single OCR pass blindly.

Uses `pytesseract.image_to_data` (word-level bounding boxes, confidence,
block/paragraph/line identifiers) rather than `image_to_string` alone —
flat text loses the spatial relationship between a label and the value next
to or below it, which is exactly what let a taxable-subtotal amount get
picked up as VAT on a real receipt where the true VAT figure was printed on
a different visual line than the flat-text output implied. Words are
reconstructed into `OcrLine`s (grouped by Tesseract's own block/paragraph/line
numbers, sorted by their horizontal position — the actual visual order on the
page, sidestepping the need for a full bidi reimplementation) that the
deterministic parser (receipt_parser.py) uses for spatial label/value
association. The flat joined text is still produced as an additional signal
(e.g. for the vision model's prompt), never the only representation.

The scoring heuristic is deliberately simple and documented as a heuristic,
not a calibrated measure of OCR accuracy: it rewards recognizable receipt
structure (known Hebrew label keywords, money-shaped number patterns) and
penalizes near-empty or garbage-heavy output. Only the single winning
candidate's lines are used to build the model prompt — candidates are never
concatenated together, so the model prompt never sees the same receipt lines
repeated several times over.
"""

import re
from dataclasses import dataclass, field

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
    ("illumination_normalized", "6"),
    ("adaptive_threshold", "6"),
    ("denoised", "6"),
)

# A label/value on the next line is only associated with this one when the
# gap between them is small relative to this line's own text height — a
# generous multiple, since receipts often have loose line spacing, but still
# bounded so an unrelated line far below is never pulled in.
LINE_PROXIMITY_HEIGHT_MULTIPLE = 1.8

_MONEY_PATTERN = re.compile(r"\d{1,3}[.,]\d{2}\b")

# Any line matching one of these is a candidate label/value line for a field
# the parser (or, for an unresolved field, the model) may still need — these
# lines are never dropped when building a compact prompt summary, regardless
# of how far down the receipt they sit.
_SUMMARY_KEYWORD_RE = re.compile(
    r'סה"?כ|לתשלום|שולם|מע"?מ|תאריך|קבלה|חשבונית|עודף|מזומן|אשראי|invoice|receipt|total|vat|date',
    re.IGNORECASE,
)
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
    "חשבונית",
    "מזומן",
    "אשראי",
    "total",
    "vat",
)


@dataclass(frozen=True)
class OcrWord:
    text: str
    left: int
    top: int
    width: int
    height: int
    conf: float


@dataclass(frozen=True)
class OcrLine:
    """A group of words Tesseract reported as sharing one (block, paragraph,
    line) — reordered by horizontal position (`left`) so `.text` reads in
    actual visual left-to-right order on the page, which is what matters for
    money amounts (always LTR) sitting next to an RTL Hebrew label."""

    words: tuple[OcrWord, ...]
    text: str
    top: int
    bottom: int
    left: int
    right: int

    @property
    def height(self) -> int:
        return max(1, self.bottom - self.top)


@dataclass(frozen=True)
class OcrCandidate:
    variant: str
    psm: str
    lines: tuple[OcrLine, ...] = field(default_factory=tuple)
    text: str = ""  # flat, line-joined text — an additional signal, never the only one
    score: float = 0.0


def score_ocr_text(text: str) -> float:
    """Heuristic only: rewards receipt-shaped structure, penalizes near-empty
    or noise-only output. Not a measure of transcription accuracy."""
    stripped = text.strip()
    if not stripped:
        return 0.0

    lower = stripped.lower()
    keyword_hits = sum(1 for kw in _KEYWORDS if kw.lower() in lower)
    money_hits = len(_MONEY_PATTERN.findall(stripped))

    recognizable_chars = sum(1 for ch in stripped if ch.isalnum() or ch in " \n.,:%-/")
    noise_ratio = 1 - (recognizable_chars / len(stripped))

    length_score = min(len(stripped) / 200, 1.0)

    score = keyword_hits * 3 + money_hits * 2 + length_score - noise_ratio * 5
    return round(score, 3)


def _build_lines(ocr_data: dict) -> tuple[OcrLine, ...]:
    groups: dict[tuple[int, int, int], list[OcrWord]] = {}
    count = len(ocr_data.get("text", []))
    for i in range(count):
        raw_text = (ocr_data["text"][i] or "").strip()
        if not raw_text:
            continue
        try:
            conf = float(ocr_data["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        if conf < 0:
            continue
        key = (ocr_data["block_num"][i], ocr_data["par_num"][i], ocr_data["line_num"][i])
        word = OcrWord(
            text=raw_text,
            left=int(ocr_data["left"][i]),
            top=int(ocr_data["top"][i]),
            width=int(ocr_data["width"][i]),
            height=int(ocr_data["height"][i]),
            conf=conf,
        )
        groups.setdefault(key, []).append(word)

    lines: list[OcrLine] = []
    for words in groups.values():
        ordered = tuple(sorted(words, key=lambda w: w.left))
        text = " ".join(w.text for w in ordered)
        top = min(w.top for w in ordered)
        bottom = max(w.top + w.height for w in ordered)
        left = min(w.left for w in ordered)
        right = max(w.left + w.width for w in ordered)
        lines.append(OcrLine(words=ordered, text=text, top=top, bottom=bottom, left=left, right=right))

    lines.sort(key=lambda line: line.top)
    return tuple(lines)


def run_ocr_candidates(variants: dict[str, Image.Image], languages: str) -> list[OcrCandidate]:
    """Runs the bounded (variant, psm) matrix against already-generated
    preprocessing variants (see image_preprocessing.generate_variants) and
    returns every candidate tried, each with its heuristic score. Never logs
    OCR text or word content — receipts may contain personal information."""
    if pytesseract is None:
        return []

    candidates: list[OcrCandidate] = []
    for variant_name, psm in CANDIDATE_CONFIGS:
        variant_image = variants.get(variant_name)
        if variant_image is None:
            continue
        try:
            ocr_data = pytesseract.image_to_data(
                variant_image,
                lang=languages,
                config=f"--psm {psm}",
                output_type=pytesseract.Output.DICT,
            )
            lines = _build_lines(ocr_data)
        except Exception:  # noqa: BLE001 - one bad config must not abort the others
            continue
        text = "\n".join(line.text for line in lines)
        candidates.append(OcrCandidate(variant_name, psm, lines, text, score_ocr_text(text)))

    return candidates


def build_ocr_summary(lines: tuple[OcrLine, ...], *, header_lines: int = 5, max_item_lines: int = 12) -> str:
    """Builds a bounded, information-preserving summary of one OCR attempt's
    lines for the vision-model prompt, instead of sending the full flat text
    of a potentially long receipt.

    Three kinds of lines are always kept, in their original top-to-bottom
    order: the first `header_lines` (where a merchant name/header usually
    sits), every line matching a recognized label keyword (total/VAT/date/
    receipt-number/currency — never dropped, since an unresolved field the
    model is still asked about must never lose its supporting text), and up
    to `max_item_lines` additional plain lines (e.g. purchased items) for
    general/category context. This bounds prompt size without ever silently
    truncating a labeled value out of the summary."""
    if not lines:
        return ""

    keep_indexes: set[int] = set(range(min(header_lines, len(lines))))
    for i, line in enumerate(lines):
        if i in keep_indexes:
            continue
        if _SUMMARY_KEYWORD_RE.search(line.text):
            keep_indexes.add(i)

    item_budget = max_item_lines
    for i, line in enumerate(lines):
        if item_budget <= 0:
            break
        if i in keep_indexes:
            continue
        keep_indexes.add(i)
        item_budget -= 1

    return "\n".join(lines[i].text for i in sorted(keep_indexes))


def select_best_ocr_candidate(image: Image.Image, languages: str) -> tuple[OcrCandidate | None, list[OcrCandidate]]:
    """Convenience entry point that generates the variants itself. Returns the
    best-scoring candidate (spatial lines + flat text) plus every candidate
    tried (for tests/diagnostics only — never logged or returned from the
    API, since it contains raw receipt text)."""
    if pytesseract is None:
        return None, []

    variants = generate_variants(image)
    candidates = run_ocr_candidates(variants, languages)
    if not candidates:
        return None, []

    best = max(candidates, key=lambda c: c.score)
    return best, candidates
