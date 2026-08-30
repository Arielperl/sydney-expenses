"""Evaluates receipt-extraction accuracy against a manually verified manifest.

Run from backend/ with the venv active:

    python -m evaluation.evaluate_receipts --manifest evaluation/manifest.json --provider mock
    python -m evaluation.evaluate_receipts --manifest evaluation/manifest.json --provider local --max-files 5
    python -m evaluation.evaluate_receipts --manifest evaluation/manifest.json --provider openai --max-files 5

Real receipts and real manifests must never be committed to git — put them in
evaluation_receipts/ and a local manifest.json, both gitignored. Only invented
data belongs in manifest.example.json.

Never prints image bytes, full receipt text, or an API key — only field-level
comparison results, timing, and counts.
"""

import argparse
import json
import time
from pathlib import Path

from app.core.config import get_settings
from app.services.extraction.exceptions import ReceiptExtractionError
from app.services.extraction.local_extractor import LocalReceiptExtractor
from app.services.extraction.mock import MockReceiptExtractor
from app.services.extraction.openai_extractor import OpenAIReceiptExtractor

FIELDS = ["business_name", "receipt_number", "date", "total", "vat", "currency", "category"]
RECEIPTS_DIR = Path(__file__).resolve().parent.parent / "evaluation_receipts"


def _normalize(value: object) -> str | None:
    if value is None:
        return None
    return str(value).strip().lower()


def _field_matches(expected: object, actual: object) -> bool:
    return _normalize(expected) == _normalize(actual)


def build_extractor(provider: str, dry_run: bool):
    if dry_run or provider == "mock":
        return MockReceiptExtractor()
    if provider == "local":
        return LocalReceiptExtractor(get_settings())
    return OpenAIReceiptExtractor(get_settings())


def _actual_fields(result) -> dict:
    category = result.category
    return {
        "business_name": result.business_name,
        "receipt_number": result.receipt_number,
        "date": result.date.isoformat() if result.date else None,
        "total": result.total,
        "vat": result.vat,
        "currency": result.currency,
        "category": category.value if hasattr(category, "value") else category,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", required=True, help="Path to a manifest JSON file")
    parser.add_argument("--provider", choices=["mock", "local", "openai"], default="mock")
    parser.add_argument(
        "--dry-run", action="store_true", help="Force the mock provider regardless of --provider (no API calls)"
    )
    parser.add_argument("--max-files", type=int, default=10, help="Maximum receipts to process (controls API cost)")
    args = parser.parse_args()

    manifest = json.loads(Path(args.manifest).read_text())
    receipts = manifest.get("receipts", [])[: args.max_files]
    if not receipts:
        print("No receipts in manifest.")
        return 0

    extractor = build_extractor(args.provider, args.dry_run)
    effective_provider = "mock" if args.dry_run else args.provider
    print(f"Evaluating {len(receipts)} receipt(s) with provider={effective_provider}\n")

    field_correct = dict.fromkeys(FIELDS, 0)
    field_total = dict.fromkeys(FIELDS, 0)
    failures = 0
    durations: list[float] = []

    for entry in receipts:
        filename = entry["filename"]
        expected = entry.get("expected", {})
        image_path = RECEIPTS_DIR / filename

        if not image_path.exists():
            print(f"  SKIP {filename}: not found in {RECEIPTS_DIR}")
            continue

        started = time.perf_counter()
        try:
            result = extractor.extract(str(image_path))
        except ReceiptExtractionError as exc:
            failures += 1
            print(f"  FAIL {filename}: extraction error ({type(exc).__name__})")
            continue
        duration = time.perf_counter() - started
        durations.append(duration)

        actual = _actual_fields(result)
        for field in FIELDS:
            if field not in expected:
                continue
            field_total[field] += 1
            if _field_matches(expected[field], actual[field]):
                field_correct[field] += 1

        print(f"  OK   {filename} ({duration:.2f}s)")

    print("\nField-level accuracy:")
    for field in FIELDS:
        total = field_total[field]
        if total == 0:
            continue
        accuracy = field_correct[field] / total
        print(f"  {field:<15} {field_correct[field]}/{total} ({accuracy:.0%})")

    if durations:
        avg = sum(durations) / len(durations)
        print(f"\nAverage processing time: {avg:.2f}s over {len(durations)} receipt(s)")
    if failures:
        print(f"Failures: {failures}")

    print(
        "\nNote: these numbers only reflect the receipts in this manifest. Do not "
        "claim general accuracy until a representative, real, manually labeled set "
        "has been evaluated."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
