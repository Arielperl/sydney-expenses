from datetime import datetime

from pydantic import BaseModel

from app.schemas.connections import ConnectionEventCounts


class WebhookEventRead(BaseModel):
    id: str
    status: str
    received_at: datetime
    processed_at: datetime | None
    failure_category: str | None
    failure_message: str | None
    sale_id: str | None
    can_reprocess: bool


class WebhookEventListResponse(BaseModel):
    events: list[WebhookEventRead]
    counts: ConnectionEventCounts
