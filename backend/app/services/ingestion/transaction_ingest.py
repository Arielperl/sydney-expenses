"""Idempotent Expense creation from an ingested transaction event.

Idempotency is enforced at the database level (a UNIQUE(source_provider,
external_id) constraint on Expense), not just an application-level
pre-check: two concurrent deliveries of the same event both attempt an
INSERT, and whichever loses the race gets an IntegrityError that this module
catches and turns into "already exists" — never a 500, and never a second
row.
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.expense import DocumentStatus, Expense, ExpenseCategory, ExpenseSource
from app.services.ingestion.webhook_provider import TransactionEvent


def find_existing(db: Session, *, source_provider: str, external_id: str) -> Expense | None:
    return (
        db.query(Expense)
        .filter(Expense.source_provider == source_provider, Expense.external_id == external_id)
        .first()
    )


def ingest_transaction_event(db: Session, event: TransactionEvent) -> tuple[Expense, bool]:
    """Returns (expense, created) — created is False when this transaction
    was already ingested (by event_id/external_transaction_id), whether from
    an earlier delivery or a concurrent one that won the race."""
    existing = find_existing(db, source_provider=event.provider, external_id=event.external_transaction_id)
    if existing is not None:
        return existing, False

    expense = Expense(
        business_name=event.merchant_name,
        amount=event.amount,
        currency=event.currency,
        category=ExpenseCategory.OTHER,
        expense_date=event.occurred_at.date(),
        payment_method=event.payment_method,
        source=ExpenseSource.WEBHOOK,
        source_provider=event.provider,
        external_id=event.external_transaction_id,
        raw_description=event.description,
        occurred_at=event.occurred_at,
        document_status=DocumentStatus.MISSING,
    )
    db.add(expense)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = find_existing(db, source_provider=event.provider, external_id=event.external_transaction_id)
        if existing is None:
            raise  # a real, unrelated integrity error — don't mask it
        return existing, False

    db.refresh(expense)
    return expense, True
