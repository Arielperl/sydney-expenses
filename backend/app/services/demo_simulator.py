"""The in-product local demo simulator — lets a reviewer generate realistic
demo sales from the app's UI instead of running a terminal command/Python
script. Every simulated sale is created through the exact same ingestion
path (`ingest_payment_event`) a real webhook delivery uses: the same VAT
calculation, the same idempotency guarantee (a fresh, unique
`external_transaction_id` per simulation), and the same document-generation
attempt. Nothing about *how* a sale is created is special-cased for demo
data — only its *labeling* is: `Sale.source = 'demo'` and
`Sale.source_provider = 'demo-simulator'`, so it can always be identified
and safely reset (see `reset_demo_data` below) without ever touching a
real manual/CSV/webhook sale.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.domain.business_time import business_now_naive
from app.models.sale import Sale, SaleSource, SaleStatus, TaxTreatment
from app.models.sale_event import SaleEvent, SaleEventSource
from app.services.documents.base import DocumentGenerationResult, DocumentProvider
from app.services.sale_service import PaymentEvent, RefundExceedsNetAmountError, ingest_payment_event, record_refund
from app.services.tax.vat import calculate_vat, vat_rate_snapshot

DEMO_SOURCE_PROVIDER = "demo-simulator"


class DemoScenario(str, Enum):
    SUCCEEDED = "succeeded"
    PENDING = "pending"
    FAILED = "failed"
    SUCCEEDED_DOCUMENT_FAILED = "succeeded_document_failed"
    SUCCEEDED_PARTIAL_REFUND = "succeeded_partial_refund"
    SUCCEEDED_FULL_REFUND = "succeeded_full_refund"


_SCENARIO_STATUS: dict[DemoScenario, SaleStatus] = {
    DemoScenario.SUCCEEDED: SaleStatus.SUCCEEDED,
    DemoScenario.PENDING: SaleStatus.PENDING,
    DemoScenario.FAILED: SaleStatus.FAILED,
    DemoScenario.SUCCEEDED_DOCUMENT_FAILED: SaleStatus.SUCCEEDED,
    DemoScenario.SUCCEEDED_PARTIAL_REFUND: SaleStatus.SUCCEEDED,
    DemoScenario.SUCCEEDED_FULL_REFUND: SaleStatus.SUCCEEDED,
}


class _AlwaysFailingDocumentProvider(DocumentProvider):
    """Used ONLY for the "document issuance fails" demo scenario, so a
    reviewer can see the Exception Center's document-failure handling
    without waiting for a real failure to occur naturally. Never used for
    a real sale."""

    def generate_document(self, sale: Sale) -> DocumentGenerationResult:
        return DocumentGenerationResult(succeeded=False, error_message="Simulated document provider failure (demo)")


class DemoSimulationError(ValueError):
    """A demo-simulation request that can't be carried out as asked (e.g. a
    partial-refund scenario on too small an amount to leave a remainder)."""


@dataclass
class DemoSimulationResult:
    sale_id: str
    scenario: DemoScenario


def simulate_sale(
    db: Session,
    *,
    customer_name: str,
    customer_contact: str | None,
    service_name: str,
    gross_amount: Decimal,
    currency: str,
    payment_method: str | None,
    tax_treatment: TaxTreatment,
    scenario: DemoScenario,
) -> DemoSimulationResult:
    status = _SCENARIO_STATUS[scenario]
    vat_amount = calculate_vat(gross_amount, tax_treatment)
    unique_id = uuid.uuid4().hex

    event = PaymentEvent(
        event_id=f"demo-{unique_id}",
        provider=DEMO_SOURCE_PROVIDER,
        external_transaction_id=f"demo-{unique_id}",
        occurred_at=business_now_naive(),
        customer_name=customer_name,
        customer_email=customer_contact,
        service_name=service_name,
        gross_amount=gross_amount,
        vat_amount=vat_amount,
        processing_fee=None,
        net_amount=None,
        currency=currency,
        payment_method=payment_method,
        status=status,
        tax_treatment=tax_treatment,
        vat_rate=vat_rate_snapshot(tax_treatment),
        description="נוצר על ידי מדמה ההדגמה המקומי (Local demo simulator)",
        sale_source=SaleSource.DEMO,
        event_source=SaleEventSource.DEMO,
    )

    document_provider = (
        _AlwaysFailingDocumentProvider() if scenario == DemoScenario.SUCCEEDED_DOCUMENT_FAILED else None
    )
    sale, _created = ingest_payment_event(db, event, document_provider=document_provider)

    if scenario == DemoScenario.SUCCEEDED_PARTIAL_REFUND:
        half = (sale.net_amount / 2).quantize(Decimal("0.01"))
        if half <= 0:
            raise DemoSimulationError("Amount is too small to simulate a partial refund")
        try:
            record_refund(db, sale, half, event_source=SaleEventSource.DEMO)
        except RefundExceedsNetAmountError as exc:  # pragma: no cover - half of net can never exceed net
            raise DemoSimulationError(str(exc)) from exc
    elif scenario == DemoScenario.SUCCEEDED_FULL_REFUND:
        record_refund(db, sale, None, event_source=SaleEventSource.DEMO)

    return DemoSimulationResult(sale_id=sale.id, scenario=scenario)


@dataclass
class DemoResetResult:
    deleted_sales_count: int
    deleted_events_count: int


def reset_demo_data(db: Session) -> DemoResetResult:
    """Deletes every sale (and its events, via the FK's ON DELETE CASCADE)
    created by this simulator — identified strictly by
    `source == SaleSource.DEMO`, never by name/date/amount heuristics — and
    nothing else. A manual, CSV-imported, or real-webhook sale is never
    touched, no matter how similar its data looks to demo data."""
    demo_sale_ids = list(db.scalars(select(Sale.id).where(Sale.source == SaleSource.DEMO)).all())
    if not demo_sale_ids:
        return DemoResetResult(deleted_sales_count=0, deleted_events_count=0)

    deleted_events_count = len(
        db.scalars(select(SaleEvent.id).where(SaleEvent.sale_id.in_(demo_sale_ids))).all()
    )

    db.execute(delete(SaleEvent).where(SaleEvent.sale_id.in_(demo_sale_ids)))
    db.execute(delete(Sale).where(Sale.source == SaleSource.DEMO))
    db.commit()

    return DemoResetResult(deleted_sales_count=len(demo_sale_ids), deleted_events_count=deleted_events_count)
