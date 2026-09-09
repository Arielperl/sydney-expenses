from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database import get_db
from app.schemas.assistant import ChatRequest, ChatResponse
from app.services.assistant.exceptions import AssistantConfigError, AssistantProviderError
from app.services.assistant.orchestrator import answer_question

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    settings = get_settings()
    history = [{"role": m.role, "content": m.content} for m in payload.history]
    try:
        reply = answer_question(settings, db, payload.message, history)
    except (AssistantConfigError, AssistantProviderError) as exc:
        raise HTTPException(
            status_code=503, detail="Could not get an answer right now. Please try again."
        ) from exc
    return ChatResponse(reply=reply)
