"""Sends one signed demo customer-payment event to a running server.

This is a *local development demo only*. For a business connection, copy the
URL and one-time secret from Imports & Connections into DEMO_WEBHOOK_URL and
DEMO_WEBHOOK_SECRET. The legacy WEBHOOK_SIGNING_SECRET flow remains supported.

Run against a locally running backend:

    cd backend && source .venv/bin/activate
    export DEMO_WEBHOOK_URL=http://localhost:8000/api/webhooks/connections/<id>
    export DEMO_WEBHOOK_SECRET=<secret shown when the connection was created>
    python -m scripts.demo_webhook_request

Re-running this script sends the *same* event_id/external_transaction_id
every time — that's deliberate, so you can see the idempotent-delivery
behavior first-hand: the first call reports created=true, every call after
that reports created=false with the same sale_id.
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from app.services.ingestion.webhook_security import compute_signature  # noqa: E402

BASE_URL = os.environ.get("DEMO_SERVER_URL", "http://localhost:8000")
WEBHOOK_URL = os.environ.get("DEMO_WEBHOOK_URL", f"{BASE_URL}/api/webhooks/payments")
SECRET = os.environ.get("DEMO_WEBHOOK_SECRET") or os.environ.get("WEBHOOK_SIGNING_SECRET", "demo-secret-change-me")

DEMO_EVENT = {
    "event_id": "demo-evt-sale-184.90-fictional",
    "provider": "demo-pay",
    "external_transaction_id": "demo-sale-184.90-fictional",
    "occurred_at": "2026-09-10T09:00:00+00:00",
    "customer_name": "Demo Fictional Customer",
    "customer_email": "demo.customer@example.com",
    "service_name": "Consulting session",
    "gross_amount": "184.90",
    # Israeli standard VAT-inclusive formula (see app/services/tax/vat.py):
    # 184.90 * 18/118 = 28.21 (rounded); net = 184.90 - 28.21 - 5.55. The
    # server independently validates this against tax_treatment and rejects
    # the request if it doesn't match — these must stay consistent.
    "vat_amount": "28.21",
    "processing_fee": "5.55",
    "net_amount": "151.14",
    "currency": "ILS",
    "payment_method": "card",
    "tax_treatment": "standard",
    "status": "succeeded",
    "description": "Demo customer payment for local testing — not a real transaction.",
}


def main() -> None:
    raw_body = json.dumps(DEMO_EVENT).encode("utf-8")
    timestamp = str(int(time.time()))
    signature = compute_signature(SECRET, timestamp, raw_body)

    response = httpx.post(
        WEBHOOK_URL,
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Signature": signature,
            "X-Timestamp": timestamp,
        },
        timeout=10.0,
    )
    print(f"status={response.status_code}")
    print(response.text)


if __name__ == "__main__":
    main()
