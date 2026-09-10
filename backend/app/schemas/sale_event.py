from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.sale_event import SaleEventSource, SaleEventType


class SaleEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sale_id: str
    event_type: SaleEventType
    source: SaleEventSource
    created_at: datetime
    event_metadata: dict | None = None
