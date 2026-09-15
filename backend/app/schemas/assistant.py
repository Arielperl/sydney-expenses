from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Must match AssistantConversation.title's column width (String(80)).
CONVERSATION_TITLE_MAX_LENGTH = 80


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = Field(default=None, max_length=36)


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str


class AssistantConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class AssistantMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    role: str
    content: str
    created_at: datetime


class AssistantConversationDetail(AssistantConversationRead):
    messages: list[AssistantMessageRead]


class AssistantConversationRename(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Generous raw ceiling — the real 1-80 rule is enforced on the trimmed
    # value below, so a request sent mostly-whitespace doesn't need to be
    # long to be rejected, and this only bounds worst-case payload size.
    title: str = Field(min_length=1, max_length=1000)

    @field_validator("title")
    @classmethod
    def _trim_and_bound(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Title cannot be empty or whitespace-only")
        if len(trimmed) > CONVERSATION_TITLE_MAX_LENGTH:
            raise ValueError(f"Title must be at most {CONVERSATION_TITLE_MAX_LENGTH} characters")
        return trimmed
