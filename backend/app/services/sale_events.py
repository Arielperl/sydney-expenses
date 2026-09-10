"""Records `SaleEvent` rows — the one place any part of the app appends to
a sale's timeline. Every call here happens inside the same database
transaction as the state change it describes (the caller commits both
together, or neither), so the timeline can never drift from what actually
happened. Never pass secrets, a full webhook body, document contents, or
more customer detail than the event itself needs into `metadata` — see
`app.models.sale_event.SaleEvent`'s own docstring.
"""

from sqlalchemy.orm import Session

from app.models.sale_event import SaleEvent, SaleEventSource, SaleEventType


def record_event(
    db: Session,
    sale_id: str,
    event_type: SaleEventType,
    source: SaleEventSource,
    metadata: dict | None = None,
) -> SaleEvent:
    event = SaleEvent(sale_id=sale_id, event_type=event_type, source=source, event_metadata=metadata)
    db.add(event)
    return event
