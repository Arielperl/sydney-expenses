from pydantic import BaseModel


class WebhookIngestResponse(BaseModel):
    created: bool
    expense_id: str
