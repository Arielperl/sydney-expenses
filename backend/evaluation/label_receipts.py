"""Interactive helper for adding new receipts to the private evaluation manifest.

Run from backend/ with the venv active:

    python -m evaluation.label_receipts
    python -m evaluation.label_receipts --provider local --model gemma3:12b

For every image in evaluation_receipts/ that isn't already in the manifest, this
runs the current extractor once, shows what it guessed field-by-field, and lets
you accept it (press Enter) or type the correct value. The manifest is written
after every receipt, so the tool is safe to stop and resume at any point.

Never prints OCR text or logs receipt content beyond the seven structured
fields being labeled — the same standard evaluate_receipts.py holds to.
"""

import argparse
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.core.config import get_settings
from app.models.expense import ExpenseCategory
from app.services.extraction.exceptions import ReceiptExtractionError
from app.services.extraction.local_extractor import LocalReceiptExtractor
from app.services.extraction.mock import MockReceiptExtractor
from app.services.extraction.openai_extractor import OpenAIReceiptExtractor

RECEIPTS_DIR = Path(__file__).resolve().parent.parent / "evaluation_receipts"
FIELDS = ["business_name", "receipt_number", "date", "total", "vat", "currency", "category"]
CATEGORY_VALUES = [c.value for c in ExpenseCategory]


def build_extractor(provider: str, model_override: str | None):
    if provider == "mock":
        return MockReceiptExtractor()
    settings = get_settings()
    if model_override and provider == "local":
        settings = settings.model_copy(update={"ollama_receipt_model": model_override})
    if provider == "local":
        return LocalReceiptExtractor(settings)
    return OpenAIReceiptExtractor(settings)


def _guessed_fields(result) -> dict:
    category = result.category
    return {
        "business_name": result.business_name,
        "receipt_number": result.receipt_number,
        "date": result.date.isoformat() if result.date else None,
        "total": str(result.total) if result.total is not None else None,
        "vat": str(result.vat) if result.vat is not None else None,
        "currency": result.currency,
        "category": category.value if hasattr(category, "value") else category,
    }


def _prompt_field(field: str, guessed: str | None) -> str | None:
    shown = guessed if guessed is not None else "(nothing — leave blank if the receipt truly has none)"
    hint = ""
    if field == "date":
        hint = " [YYYY-MM-DD]"
    elif field == "category":
        hint = f" [one of: {', '.join(CATEGORY_VALUES)}]"
    while True:
        raw = input(f"  {field}{hint} — guessed: {shown}\n    > ").strip()
        if raw == "":
            return guessed
        if raw.lower() in ("-", "none", "null"):
            return None
        if field == "category" and raw not in CATEGORY_VALUES:
            print(f"    not a valid category, pick one of: {', '.join(CATEGORY_VALUES)}")
            continue
        if field in ("total", "vat"):
            try:
                Decimal(raw)
            except InvalidOperation:
                print("    not a valid number, try again")
                continue
        return raw


def label_one(extractor, path: Path) -> dict | None:
    print(f"\n--- {path.name} ---")
    try:
        result = extractor.extract(str(path))
        guessed = _guessed_fields(result)
    except ReceiptExtractionError as exc:
        print(f"  extraction failed ({type(exc).__name__}) — you'll need to fill in every field by hand.")
        guessed = dict.fromkeys(FIELDS)

    expected = {}
    for field in FIELDS:
        value = _prompt_field(field, guessed.get(field))
        expected[field] = value

    confirm = input("  save this entry? [Y/n] ").strip().lower()
    if confirm == "n":
        print("  skipped.")
        return None
    return {"filename": path.name, "expected": expected}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", default="evaluation/manifest.json")
    parser.add_argument("--provider", choices=["mock", "local", "openai"], default="local")
    parser.add_argument("--model", default=None, help="Override OLLAMA_RECEIPT_MODEL for this run only.")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"receipts": []}
    labeled_names = {entry["filename"] for entry in manifest["receipts"]}

    candidates = sorted(
        f
        for f in RECEIPTS_DIR.iterdir()
        if f.is_file() and not f.name.startswith(".") and f.name not in labeled_names
    )
    if not candidates:
        print("Nothing new to label — every file in evaluation_receipts/ is already in the manifest.")
        return 0

    print(f"{len(candidates)} new receipt(s) to label. Press Ctrl+C any time — progress is saved after each one.\n")
    extractor = build_extractor(args.provider, args.model)

    for path in candidates:
        entry = label_one(extractor, path)
        if entry is not None:
            manifest["receipts"].append(entry)
            manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"  saved. ({len(manifest['receipts'])} total in manifest)")

    print(f"\nDone. {len(manifest['receipts'])} receipt(s) now in {manifest_path}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
