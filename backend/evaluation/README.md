# Receipt extraction evaluation

A small local tool for measuring how accurately a `ReceiptExtractor` reads real
receipts, field by field. It is **not** part of the test suite (which only uses
mocked/fake clients and never touches this tool) — it's a manual accuracy check
you run yourself against your own receipts.

## Setup

1. Create a local, gitignored directory for real receipt images:

   ```bash
   mkdir -p backend/evaluation_receipts
   # copy your own receipt images in here
   ```

2. Copy the example manifest and fill in the **manually verified** expected
   values for each receipt you added:

   ```bash
   cp backend/evaluation/manifest.example.json backend/evaluation/manifest.json
   ```

   Edit `manifest.json` — each entry maps a filename (resolved inside
   `evaluation_receipts/`) to the expected `business_name`, `receipt_number`,
   `date` (`YYYY-MM-DD`), `total`, `vat`, `currency`, and `category`. Use `null`
   for a field the receipt genuinely doesn't have.

   **`evaluation_receipts/` and `manifest.json` are both gitignored — never
   commit real receipt images or their manually labeled data.** Only
   `manifest.example.json` (invented data) is tracked in git.

## Running it

```bash
cd backend && source .venv/bin/activate

# Mock provider — no API key needed, no network calls, safe to run anytime:
python -m evaluation.evaluate_receipts --manifest evaluation/manifest.json --provider mock

# Local provider — free, fully offline (Tesseract OCR + a local Ollama model).
# Requires Ollama running (`ollama serve`) with the model pulled beforehand.
# Slower per receipt than the other two (a 12B local model on a laptop), so
# --max-files still matters for how long a run takes, even though it's free.
python -m evaluation.evaluate_receipts --manifest evaluation/manifest.json --provider local --max-files 5

# Real OpenAI provider — costs money per receipt, requires OPENAI_API_KEY/
# OPENAI_RECEIPT_MODEL in backend/.env. --max-files caps the cost.
python -m evaluation.evaluate_receipts --manifest evaluation/manifest.json --provider openai --max-files 5

# Force mock regardless of --provider (e.g. to sanity-check the tool itself):
python -m evaluation.evaluate_receipts --manifest evaluation/manifest.json --dry-run
```

## Interpreting the output

For each field present in at least one manifest entry's `expected` object, the
tool reports `correct/total (percentage)` — an exact string match after
trimming whitespace and normalizing case. It also reports average processing
time per receipt and any hard extraction failures.

This is a **small, self-labeled sample accuracy**, not a calibrated statistic —
treat it as a smoke test and a way to compare mock vs. a specific model/prompt
version, not as a claim about real-world accuracy. Do not report or advertise
an accuracy number until you've run this against a reasonably sized, real,
manually labeled set of receipts.

The tool never prints image bytes, full receipt text, or an API key — only
filenames, per-field match results, and timing.
