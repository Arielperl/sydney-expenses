from pydantic import BaseModel


class WebhookIngestResponse(BaseModel):
    created: bool
    sale_id: str
