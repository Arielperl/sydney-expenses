"""Cardcom account-level ("LowProfile"/"אישורית זהב") webhook adapter.

Unlike Grow, Cardcom's own documentation explicitly forbids trusting the raw
webhook delivery at all: "לצורך אבטחת מידע ומניעת התחזות — חובה לאחר קבלת
פרטי העסקה יש לפנות אל שרתי קארדקום ביוזמתנו לבדיקת הנתונים" ("for security
and anti-impersonation, you must proactively contact Cardcom's own servers to
verify the data") — see
https://cardcomapi.zendesk.com/hc/he/articles/25264402497426 ("Step 1+2 —
Create payment page & get the result of an Iframe/Redirect deal"). This
module therefore has two jobs, kept deliberately separate:

1. `extract_low_profile_id` — pull *only* the `LowProfileId` (Cardcom's
   transaction reference) out of whatever the raw webhook delivery contains
   (JSON or form-encoded — Cardcom's docs show both content types across
   their different webhook formats). Nothing else from the raw delivery is
   ever used for anything financial.
2. `CardcomVerificationClient.get_lowprofile_result` + `parse_lowprofile_result`
   — call Cardcom's own `POST /api/v11/LowProfile/GetLpResult` server-to-
   server with our own stored terminal credentials, and build the `Sale`
   fields *only* from that authoritative, verified response.

Scope: only `ChargeOnly`, `ChargeAndCreateToken`, and `Do3DSAndSubmit` are
treated as real, revenue-or-decline transactions — `CreateTokenOnly` and
`SuspendedDeal` (an authorization hold, not a completed charge) never move
money and are rejected as out of scope, never silently turned into a sale.
A successful verification (`TranzactionInfo.ResponseCode == 0`) becomes a
`succeeded` sale; any other `TranzactionInfo.ResponseCode` (a decline) still
becomes a `Sale`, but with `status=failed` — visible in the Exception
Center, never counted as revenue (`Sale.revenue_contribution()` already
returns 0 for a failed sale) — never silently dropped.

PII/security:
- Card fields (brand, last-4, issuer, acquirer, RRN, token) are read from
  Cardcom's response only to be discarded — never stored on the `Sale`,
  never logged. `payment_method` is a fixed, generic `"card"`.
- Cardcom's terminal `ApiName`/`ApiPassword` are read only from the
  connection's own encrypted, per-business credential record (see
  app/models/cardcom_credential.py) — never hardcoded, never logged.
- No refund/cancellation ingestion is implemented — Cardcom's own decline-
  reporting is a *separate*, explicitly opt-in merchant setting ("תמיד בצע
  דיווח של עסקה"), and refund/cancellation webhooks are a distinct,
  undocumented-for-this-integration format; see README.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

import httpx

from app.models.sale import SaleSource, SaleStatus, TaxTreatment
from app.models.sale_event import SaleEventSource
from app.schemas.validators import validate_transaction_datetime_reasonable
from app.services.sale_service import PaymentEvent
from app.services.tax.vat import calculate_vat, vat_rate_snapshot

CARDCOM_CURRENCY_BY_COIN_ID = {1: "ILS", 2: "USD"}
# Real, completed-charge operations only — see module docstring.
CHARGING_OPERATIONS = {"ChargeOnly", "ChargeAndCreateToken", "Do3DSAndSubmit"}
MAX_MONEY = Decimal("9999999999.99")


class CardcomPayloadError(ValueError):
    """The raw webhook delivery didn't contain a usable LowProfileId."""


class CardcomVerificationError(RuntimeError):
    """Cardcom's own GetLpResult verification call failed, timed out, or
    returned a response this adapter cannot safely act on. Always treated
    as retryable/reprocessable — never as "verified failed" (a decline is a
    *successful* verification with a negative result, not this)."""


class CardcomUnsupportedOperationError(ValueError):
    """A verified, real Cardcom response, but for an operation that never
    moves money (CreateTokenOnly, SuspendedDeal) — out of this
    integration's scope, never turned into a sale either way."""


def extract_low_profile_id(payload: dict) -> str:
    """Reads only `LowProfileId` out of a raw, UNVERIFIED webhook delivery
    (already parsed from either JSON or form-encoded body by the route —
    see app/api/routes/webhooks.py). Deliberately reads nothing else:
    every other field in the raw delivery is untrusted per Cardcom's own
    documentation (see module docstring)."""
    value = payload.get("LowProfileId") or payload.get("lowprofileid") or payload.get("LowProfileID")
    if not isinstance(value, str) or not value.strip():
        raise CardcomPayloadError("'LowProfileId' is required and must be a non-empty string")
    value = value.strip()
    if len(value) > 100 or any(ord(character) < 32 for character in value):
        raise CardcomPayloadError("'LowProfileId' is not a valid transaction reference")
    return value


@dataclass
class CardcomCredentials:
    terminal_number: str
    api_name: str
    api_password: str | None = None


class CardcomVerificationClient:
    """Thin wrapper around Cardcom's LowProfile/GetLpResult call — isolated
    so it can be mocked in tests without a real network call."""

    def __init__(self, *, base_url: str, timeout_seconds: float):
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def get_lowprofile_result(self, credentials: CardcomCredentials, low_profile_id: str) -> dict:
        request_body = {
            "TerminalNumber": credentials.terminal_number,
            "ApiName": credentials.api_name,
            "LowProfileId": low_profile_id,
        }
        try:
            response = httpx.post(
                f"{self._base_url}/api/v11/LowProfile/GetLpResult",
                json=request_body,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise CardcomVerificationError(f"Cardcom verification call failed: {type(exc).__name__}") from exc
        except ValueError as exc:  # JSON decode failure
            raise CardcomVerificationError("Cardcom verification call returned an invalid response") from exc


def _parse_amount(raw) -> Decimal:
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise CardcomVerificationError(f"Cardcom returned an unusable transaction amount: {raw!r}") from exc
    if not value.is_finite() or value < 0 or value > MAX_MONEY:
        raise CardcomVerificationError(f"Cardcom returned an implausible transaction amount: {raw!r}")
    return value


def _parse_create_date(raw: str) -> datetime:
    """Cardcom's `CreateDate` (e.g. "2025-03-12T08:46:45") carries no
    timezone marker — per this app's naive-timestamp convention
    (app.domain.business_time), treated as already business-local
    wall-clock time, the same as any other timezone-less source."""
    try:
        occurred_at = datetime.fromisoformat(raw)
    except (ValueError, TypeError) as exc:
        raise CardcomVerificationError(f"Cardcom returned an unusable CreateDate: {raw!r}") from exc
    try:
        validate_transaction_datetime_reasonable(occurred_at)
    except ValueError as exc:
        raise CardcomVerificationError(str(exc)) from exc
    return occurred_at


def _clean_optional(value) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def parse_lowprofile_result(result: dict) -> PaymentEvent:
    """Builds a `PaymentEvent` from an already-fetched, authoritative
    `GetLpResult` response. Raises `CardcomVerificationError` for a response
    that cannot be trusted/acted on (safely reprocessable — see
    app/services/webhook_events.py), or `CardcomUnsupportedOperationError`
    for a real but out-of-scope operation (never reprocessable — there is
    nothing to charge)."""
    if not isinstance(result, dict):
        raise CardcomVerificationError("GetLpResult response is not a JSON object")

    top_response_code = result.get("ResponseCode")
    if top_response_code != 0:
        raise CardcomVerificationError(f"GetLpResult call itself failed: ResponseCode={top_response_code!r}")

    operation = result.get("Operation")
    if operation not in CHARGING_OPERATIONS:
        raise CardcomUnsupportedOperationError(f"'{operation}' is not a chargeable Cardcom operation")

    tranz_info = result.get("TranzactionInfo")
    if not isinstance(tranz_info, dict):
        # A charging operation whose transaction details aren't available yet
        # (e.g. still in progress) — genuinely not yet verifiable, not a
        # confirmed decline. Retry later via reprocess.
        raise CardcomVerificationError("GetLpResult returned no TranzactionInfo for a charging operation")

    low_profile_id = result.get("LowProfileId")
    tranz_id = tranz_info.get("TranzactionId") or result.get("TranzactionId")
    external_id = str(tranz_id) if tranz_id else f"lpid:{low_profile_id}"

    tranz_response_code = tranz_info.get("ResponseCode")
    status = SaleStatus.SUCCEEDED if tranz_response_code == 0 else SaleStatus.FAILED

    amount_raw = tranz_info.get("Amount")
    gross_amount = _parse_amount(amount_raw) if amount_raw is not None else Decimal("0")

    currency = CARDCOM_CURRENCY_BY_COIN_ID.get(tranz_info.get("CoinId"), "ILS")

    create_date_raw = tranz_info.get("CreateDate")
    occurred_at = _parse_create_date(create_date_raw) if create_date_raw else _parse_create_date(
        datetime.utcnow().isoformat(timespec="seconds")
    )

    customer_name = (
        _clean_optional(tranz_info.get("CardOwnerName")) or "לקוח Cardcom"
    )
    customer_email = _clean_optional(tranz_info.get("CardOwnerEmail"))
    customer_phone = _clean_optional(tranz_info.get("CardOwnerPhone"))
    customer_contact = customer_email or customer_phone

    tax_treatment = TaxTreatment.STANDARD
    vat_amount = calculate_vat(gross_amount, tax_treatment) if gross_amount > 0 else Decimal("0")
    net_amount = gross_amount - vat_amount

    return PaymentEvent(
        event_id=external_id,
        provider="cardcom",
        external_transaction_id=external_id,
        occurred_at=occurred_at,
        customer_name=customer_name,
        customer_email=customer_contact,
        service_name="עסקת Cardcom",
        gross_amount=gross_amount,
        vat_amount=vat_amount,
        processing_fee=None,
        net_amount=net_amount,
        currency=currency,
        payment_method="card",
        status=status,
        tax_treatment=tax_treatment,
        vat_rate=vat_rate_snapshot(tax_treatment),
        description=None,
        sale_source=SaleSource.WEBHOOK,
        event_source=SaleEventSource.WEBHOOK,
    )
