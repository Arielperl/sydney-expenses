import hashlib
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from app.models.expense import ExpenseCategory
from app.schemas.receipt import ExtractedReceiptData
from app.services.extraction.base import ReceiptExtractor

_SAMPLE_BUSINESSES: list[tuple[str, ExpenseCategory]] = [
    ("Shufersal", ExpenseCategory.GROCERIES),
    ("Rami Levy", ExpenseCategory.GROCERIES),
    ("Cofix", ExpenseCategory.DINING),
    ("Super-Pharm", ExpenseCategory.HEALTH),
    ("Paz Gas Station", ExpenseCategory.TRANSPORT),
    ("Ace Hardware", ExpenseCategory.SHOPPING),
    ("Cinema City", ExpenseCategory.ENTERTAINMENT),
]


class MockReceiptExtractor(ReceiptExtractor):
    """Deterministic offline stand-in for a real Vision AI extraction provider.

    Produces plausible-but-clearly-mocked results derived from the image bytes so the
    same file always yields the same output. Never invents a receipt number or VAT
    figure it isn't reasonably sure of; those are left blank with a warning instead.
    """

    def extract(self, image_path: str) -> ExtractedReceiptData:
        path = Path(image_path)
        digest = self._digest_for(path)
        seed = int.from_bytes(digest[:4], byteorder="big")

        business_name, category = _SAMPLE_BUSINESSES[seed % len(_SAMPLE_BUSINESSES)]
        amount = (Decimal(15) + Decimal(seed % 48000) / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        vat_rate = Decimal("0.17")
        has_receipt_number = (seed >> 8) % 3 != 0
        has_vat = (seed >> 10) % 4 != 0
        days_ago = (seed >> 12) % 14
        confidence = round(0.55 + ((seed >> 16) % 40) / 100, 2)

        # Warnings are stable machine-readable codes, not English sentences, so the
        # frontend can render them translated in whichever language is active.
        warnings: list[str] = []
        receipt_number = None
        if has_receipt_number:
            receipt_number = str(10000 + (seed % 90000))
        else:
            warnings.append("receipt_number_not_confident")

        vat_amount = None
        if has_vat:
            vat_amount = (amount * vat_rate / (1 + vat_rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            warnings.append("vat_amount_not_confident")

        return ExtractedReceiptData(
            business_name=business_name,
            receipt_number=receipt_number,
            date=date.today() - timedelta(days=days_ago),
            total=amount,
            vat=vat_amount,
            currency="ILS",
            category=category,
            confidence=confidence,
            warnings=warnings,
        )

    @staticmethod
    def _digest_for(path: Path) -> bytes:
        if path.exists():
            return hashlib.sha256(path.read_bytes()).digest()
        return hashlib.sha256(str(path).encode("utf-8")).digest()
