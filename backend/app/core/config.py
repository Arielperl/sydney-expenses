from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    # An absolute path, not ".env" — a relative path here resolves against the
    # process's OS working directory, which does not always match backend/
    # (e.g. when uvicorn is launched from the repo root with --app-dir backend,
    # as .claude/launch.json does). That mismatch used to fail silently: no
    # .env was found, so every setting silently fell back to its code default
    # (mock extraction, default CORS origins) with no error at all.
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Receiptly API"
    database_url: str = f"sqlite:///{BACKEND_DIR / 'receiptly.db'}"
    uploads_dir: str = str(BACKEND_DIR / "uploads")
    max_upload_size_bytes: int = 10 * 1024 * 1024  # 10 MB
    allowed_image_content_types: set[str] = {"image/jpeg", "image/png", "image/webp"}
    cors_allowed_origins: list[str] = ["http://localhost:5173"]
    default_currency: str = "ILS"
    pending_upload_expiry_hours: int = 24

    # Receipt extraction provider. "mock" (default) needs no external credentials and
    # never leaves the machine; "local" runs Tesseract OCR + a local Ollama model,
    # never leaving the machine either; "openai" sends the receipt image to OpenAI.
    receipt_extractor_provider: Literal["mock", "local", "openai"] = "mock"
    openai_api_key: str | None = None
    openai_receipt_model: str | None = None
    openai_timeout_seconds: float = 30.0
    openai_max_retries: int = 2
    # Separate from openai_receipt_model: the assistant chat is a text/tool-calling
    # task, never vision, so it always uses the cheaper mini model regardless of
    # which (possibly more expensive) model OPENAI_RECEIPT_MODEL is set to.
    openai_assistant_model: str = "gpt-4o-mini"

    ollama_base_url: str = "http://localhost:11434"
    # Re-evaluated after making local extraction deterministic-first (most
    # factual fields now come from the OCR/spatial parser, not the vision
    # model — see local_extractor.py): on the same private 4-receipt
    # manifest, gemma3:12b and qwen3-vl:8b now produce IDENTICAL field-level
    # accuracy (receipt_number 67%, date 75%, total 100%, vat 75%, currency
    # 100%, category 50%, exact-match 1/4 for both), since the fields that
    # used to differentiate them are largely parser-resolved for both models
    # alike. With accuracy equal, gemma3:12b is preferred for its materially
    # lower latency (~30s vs ~62s average on this manifest). Still fully
    # configurable — set OLLAMA_RECEIPT_MODEL=qwen3-vl:8b to use the other.
    ollama_receipt_model: str = "gemma3:12b"
    ollama_timeout_seconds: float = 120.0
    ollama_max_retries: int = 2
    # Explicitly requested rather than left at each model's own Ollama
    # default: some vision models default to a small context window (observed:
    # 4096 tokens) that overflows once the original photo, the enhanced
    # image, and the full instruction/OCR-hint prompt are all included —
    # the request fails outright (HTTP 400) rather than degrading gracefully.
    # A larger context window uses more RAM/VRAM while the model is loaded.
    # A tall receipt photo (crop-corrected, then upscaled to the target OCR
    # width) plus the full instruction/OCR-hint prompt was observed to need
    # more than 8192 tokens for at least one real receipt — 16384 is a
    # deliberate middle ground, not the largest possible value.
    ollama_num_ctx: int = 16384
    # Also explicit rather than left at Ollama's own default: a verbose
    # "thinking"-style model can be cut off mid-JSON before ever reaching a
    # valid closing brace if the output token budget is too small (observed:
    # Ollama's default max output length truncated a receipt's warnings list
    # before the required fields even finished).
    #
    # Sized against ollama_timeout_seconds, not just picked generously: gemma3:12b
    # was measured generating at a steady ~12 tokens/second on this hardware (see
    # README "Local model choice"). At the previous default of 2048, a request that
    # actually needed the full budget took ~170s to reach it — LONGER than the
    # 120s client timeout below, so a request that should have failed cleanly (a
    # truncated-but-returned response) instead always hit a network timeout first,
    # got retried up to ollama_max_retries times, and could take 6+ minutes to
    # finally give up. 768 tokens (~64s of generation, leaving real margin for
    # image encoding and prompt processing within the 120s budget) is far more
    # than any real, successful extraction has ever needed, while ensuring a
    # response that genuinely can't converge (observed for real on a specific
    # image, deterministically reproducible) fails via a fast, clean token-cap
    # truncation instead of a slow multi-attempt timeout cascade.
    ollama_num_predict: int = 768
    # Used instead of ollama_num_ctx/ollama_num_predict when the deterministic
    # OCR/spatial parser has already confidently resolved every factual field
    # (receipt_number, date, total, vat, currency) and the model is asked only
    # for the two remaining semantic fields (business_name, category) — a much
    # smaller JSON schema that reliably completes in far less generation time
    # for a well-behaved model. Verified empirically (not guessed) against a
    # real receipt before being set: gemma3:12b completes reliably in ~12s at
    # these values, but a *reduced context window* specifically was measured
    # to make qwen3-vl:8b's "thinking" behavior hang for 180s+ rather than
    # degrade gracefully on the same request — a materially worse outcome
    # than the full path, and the reason ollama_num_ctx_fast is kept equal to
    # ollama_num_ctx (no reduction) rather than also shrunk. A too-small
    # ollama_num_predict_fast is a *safer* failure mode (a parse error,
    # automatically retried once at the full budget — see
    # LocalReceiptExtractor.extract) than a hung/timed-out request, which is
    # why only num_predict is reduced here, never num_ctx. See README "Local
    # model choice" for the measured latency this produced.
    ollama_num_ctx_fast: int = 16384
    ollama_num_predict_fast: int = 512
    # Deterministic sampling: temperature=0 always picks the highest-probability
    # token, and a fixed seed makes that choice reproducible run-to-run on the
    # same input — both were previously left unset (Ollama's own per-model
    # defaults), which is a real source of the run-to-run field-level variance
    # observed on identical inputs (see README). Configurable rather than
    # hardcoded so a specific deployment can restore sampling if it ever needs
    # to (e.g. to compare against non-deterministic output).
    ollama_temperature: float = 0.0
    ollama_seed: int = 42
    tesseract_languages: str = "heb+eng"

    # Receipt image storage provider. "local" (default) writes to uploads_dir on
    # disk and needs no external credentials — the safe default for a fresh clone
    # and for the automated test suite. "supabase" stores images in a private
    # Supabase Storage bucket, served back to the frontend only via freshly
    # generated, time-limited signed URLs (never a permanent public URL).
    storage_provider: Literal["local", "supabase"] = "local"
    supabase_url: str | None = None
    supabase_secret_key: str | None = None
    supabase_storage_bucket: str | None = None
    supabase_signed_url_ttl_seconds: int = 3600


class StorageConfigurationError(RuntimeError):
    """Raised at startup when STORAGE_PROVIDER=supabase but required Supabase
    configuration is missing. Deliberately fails fast rather than silently
    falling back to local storage, so a misconfigured deployment never
    surprises an operator by writing receipts to an ephemeral local disk."""


def validate_storage_settings(settings: Settings) -> None:
    if settings.storage_provider != "supabase":
        return
    missing = [
        name
        for name, value in (
            ("SUPABASE_URL", settings.supabase_url),
            ("SUPABASE_SECRET_KEY", settings.supabase_secret_key),
            ("SUPABASE_STORAGE_BUCKET", settings.supabase_storage_bucket),
        )
        if not value
    ]
    if missing:
        raise StorageConfigurationError(
            "STORAGE_PROVIDER=supabase requires the following environment "
            f"variable(s) to be set: {', '.join(missing)}."
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
