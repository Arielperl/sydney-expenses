"""Core sale lifecycle: creating a sale (from any source), attempting to
issue its customer document, and recording refunds. Every creation path
(webhook, CSV import, manual entry) funnels through `finalize_new_sale` so
the document-issuance attempt and its honesty rules apply uniformly.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.sale import DocumentStatus, Sale, SaleSource, SaleStatus, TaxTreatment
from app.models.sale_event import SaleEventSource, SaleEventType
from app.services.documents import DocumentProvider, get_document_provider
from app.services.sale_events import record_event

logger = logging.getLogger(__name__)

_STATUS_EVENT_TYPE = {
    SaleStatus.SUCCEEDED: SaleEventType.PAYMENT_SUCCEEDED,
    SaleStatus.PENDING: SaleEventType.PAYMENT_PENDING,
    SaleStatus.FAILED: SaleEventType.PAYMENT_FAILED,
}


class RefundExceedsNetAmountError(Exception):
    pass


def compute_net_amount(gross_amount: Decimal, vat_amount: Decimal | None, processing_fee: Decimal | None) -> Decimal:
    return gross_amount - (vat_amount or Decimal("0")) - (processing_fee or Decimal("0"))


def finalize_new_sale(
    db: Session,
    sale: Sale,
    *,
    document_provider: DocumentProvider | None = None,
    event_source: SaleEventSource = SaleEventSource.MANUAL,
    creation_event_type: SaleEventType = SaleEventType.SALE_CREATED_MANUALLY,
) -> Sale:
    """Persists a brand-new `Sale`, records its creation and initial-status
    events in the same transaction, and — if it's a completed sale —
    attempts to issue its customer document via the configured (today:
    demo-only) provider. A document-generation failure never blocks the
    sale itself from being recorded — it just leaves
    `document_status='failed'` for the exception center to surface."""
    db.add(sale)
    db.flush()  # assigns sale.id so the events below can reference it
    record_event(db, sale.id, creation_event_type, event_source)
    status_event_type = _STATUS_EVENT_TYPE.get(sale.status)
    if status_event_type is not None:
        record_event(db, sale.id, status_event_type, event_source)
    db.commit()
    db.refresh(sale)

    if sale.status == SaleStatus.SUCCEEDED:
        attempt_document_generation(db, sale, document_provider or get_document_provider(), event_source=event_source)

    return sale


def attempt_document_generation(
    db: Session,
    sale: Sale,
    provider: DocumentProvider | None = None,
    *,
    event_source: SaleEventSource = SaleEventSource.SYSTEM,
) -> None:
    """Standalone entry point for triggering document generation on an
    already-persisted sale, outside of `finalize_new_sale` — used by
    creation paths (like the CSV batch importer) that need to control their
    own transaction/savepoint boundaries around the row-level insert."""
    provider = provider or get_document_provider()
    record_event(db, sale.id, SaleEventType.DOCUMENT_ISSUANCE_ATTEMPTED, SaleEventSource.SYSTEM)
    try:
        result = provider.generate_document(sale)
    except Exception as exc:  # noqa: BLE001 - a provider failure must never crash sale creation
        logger.info("document_generation_error sale_id=%s error_category=%s", sale.id, type(exc).__name__)
        sale.document_status = DocumentStatus.FAILED
        record_event(db, sale.id, SaleEventType.DOCUMENT_ISSUANCE_FAILED, SaleEventSource.SYSTEM, {"reason": type(exc).__name__})
        db.commit()
        return

    if result.succeeded:
        sale.document_status = DocumentStatus.ISSUED
        sale.document_number = result.document_number
        sale.document_url = result.document_url
        record_event(
            db, sale.id, SaleEventType.DOCUMENT_ISSUED, SaleEventSource.SYSTEM,
            {"document_number": result.document_number} if result.document_number else None,
        )
    else:
        sale.document_status = DocumentStatus.FAILED
        record_event(
            db, sale.id, SaleEventType.DOCUMENT_ISSUANCE_FAILED, SaleEventSource.SYSTEM,
            {"reason": result.error_message} if result.error_message else None,
        )
    db.commit()


def record_refund(
    db: Session,
    sale: Sale,
    amount: Decimal | None,
    *,
    event_source: SaleEventSource = SaleEventSource.MANUAL,
) -> Sale:
    """Records a full or partial refund. `amount` omitted means a full
    refund. Idempotent in the sense that refunding an already-fully-refunded
    sale again is a safe no-op, not a double-deduction — and records no
    duplicate event for that no-op."""
    if sale.status == SaleStatus.REFUNDED:
        return sale

    already_refunded = sale.refunded_amount or Decimal("0")
    if amount is None:
        sale.refunded_amount = sale.net_amount
        sale.status = SaleStatus.REFUNDED
        event_type = SaleEventType.REFUND_FULL
        recorded_amount = sale.net_amount - already_refunded
    else:
        new_total = already_refunded + amount
        if new_total > sale.net_amount:
            raise RefundExceedsNetAmountError("refund amount would exceed the sale's net amount")
        sale.refunded_amount = new_total
        sale.status = SaleStatus.REFUNDED if new_total == sale.net_amount else SaleStatus.PARTIALLY_REFUNDED
        event_type = SaleEventType.REFUND_FULL if sale.status == SaleStatus.REFUNDED else SaleEventType.REFUND_PARTIAL
        recorded_amount = amount

    record_event(
        db, sale.id, event_type, event_source,
        {"amount": str(recorded_amount), "currency": sale.currency},
    )
    db.commit()
    db.refresh(sale)
    return sale


@dataclass
class PaymentEvent:
    event_id: str
    provider: str
    external_transaction_id: str
    occurred_at: datetime
    customer_name: str
    customer_email: str | None
    service_name: str
    gross_amount: Decimal
    vat_amount: Decimal | None
    processing_fee: Decimal | None
    net_amount: Decimal | None
    currency: str
    payment_method: str | None
    status: SaleStatus
    tax_treatment: TaxTreatment
    vat_rate: Decimal | None
    description: str | None = None
    # A real payment provider webhook vs. the in-product demo simulator
    # (app/services/demo_simulator.py) — both flow through this same
    # dataclass and `ingest_payment_event`, but must be labeled distinctly
    # so demo data can always be identified (and safely reset) without
    # touching a real webhook-ingested sale.
    sale_source: SaleSource = SaleSource.WEBHOOK
    event_source: SaleEventSource = SaleEventSource.WEBHOOK


def find_existing_sale(db: Session, *, source_provider: str, external_id: str) -> Sale | None:
    return (
        db.query(Sale)
        .filter(Sale.source_provider == source_provider, Sale.external_id == external_id)
        .first()
    )


def ingest_payment_event(
    db: Session, event: PaymentEvent, *, document_provider: DocumentProvider | None = None
) -> tuple[Sale, bool]:
    """Returns (sale, created) — created is False when this payment event
    was already ingested, whether from an earlier delivery or a concurrent
    one that won the idempotency race. Idempotency is enforced at the
    database level via UNIQUE(source_provider, external_id), not just an
    application-level pre-check."""
    existing = find_existing_sale(db, source_provider=event.provider, external_id=event.external_transaction_id)
    if existing is not None:
        return existing, False

    net_amount = event.net_amount
    if net_amount is None:
        net_amount = compute_net_amount(event.gross_amount, event.vat_amount, event.processing_fee)

    sale = Sale(
        external_id=event.external_transaction_id,
        source_provider=event.provider,
        source=event.sale_source,
        status=event.status,
        occurred_at=event.occurred_at,
        customer_name=event.customer_name,
        customer_contact=event.customer_email,
        service_name=event.service_name,
        gross_amount=event.gross_amount,
        vat_amount=event.vat_amount,
        tax_treatment=event.tax_treatment,
        vat_rate=event.vat_rate,
        processing_fee=event.processing_fee,
        net_amount=net_amount,
        currency=event.currency,
        payment_method=event.payment_method,
        raw_description=event.description,
        document_status=DocumentStatus.PENDING,
    )
    try:
        finalized = finalize_new_sale(
            db,
            sale,
            document_provider=document_provider,
            event_source=event.event_source,
            creation_event_type=SaleEventType.SALE_RECEIVED,
        )
    except IntegrityError:
        db.rollback()
        existing = find_existing_sale(db, source_provider=event.provider, external_id=event.external_transaction_id)
        if existing is None:
            raise  # a real, unrelated integrity error — don't mask it
        return existing, False

    return finalized, True
