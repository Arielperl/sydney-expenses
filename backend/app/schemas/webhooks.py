from pydantic import BaseModel


class WebhookIngestResponse(BaseModel):
    created: bool
    # Null only for a Grow delivery that was durably received but failed
    # during processing (see app/services/webhook_events.py) — `event_id`
    # identifies the durable inbox row in that case, for the owner's
    # connection activity view / safe reprocessing, instead of a sale.
    sale_id: str | None = None
    event_id: str | None = None
