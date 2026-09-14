from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rate_limit import RateLimiter, client_ip
from app.database import get_db
from app.models.assistant_conversation import AssistantConversation, AssistantMessage
from app.schemas.assistant import (
    AssistantConversationDetail,
    AssistantConversationRead,
    ChatRequest,
    ChatResponse,
)
from app.services.assistant.exceptions import AssistantConfigError, AssistantProviderError
from app.services.assistant.orchestrator import answer_question

router = APIRouter(prefix="/assistant", tags=["assistant"])

# One turn can trigger several paid provider calls. Keep the existing bounded
# budget, scoped to both business and user where authentication is enabled.
_chat_by_ip = RateLimiter(max_requests=30, window_seconds=300)
_LOCAL_USER_ID = "local-demo-user"
_HISTORY_LIMIT = 40
_CONVERSATION_LIST_LIMIT = 50


def _user_id(request: Request) -> str:
    return getattr(request.state, "user", {}).get("id") or _LOCAL_USER_ID


def _conversation_or_404(db: Session, conversation_id: str, user_id: str) -> AssistantConversation:
    conversation = db.scalar(
        select(AssistantConversation).where(
            AssistantConversation.id == conversation_id,
            AssistantConversation.user_id == user_id,
        )
    )
    if conversation is None:
        # Do not reveal whether the id belongs to another user or business.
        raise HTTPException(status_code=404, detail="השיחה לא נמצאה")
    return conversation


def _title_from_message(message: str) -> str:
    normalized = " ".join(message.split())
    return normalized[:60] + ("…" if len(normalized) > 60 else "")


@router.get("/conversations", response_model=list[AssistantConversationRead])
def list_conversations(request: Request, db: Session = Depends(get_db)):
    return db.scalars(
        select(AssistantConversation)
        .where(AssistantConversation.user_id == _user_id(request))
        .order_by(AssistantConversation.updated_at.desc())
        .limit(_CONVERSATION_LIST_LIMIT)
    ).all()


@router.get("/conversations/{conversation_id}", response_model=AssistantConversationDetail)
def get_conversation(conversation_id: str, request: Request, db: Session = Depends(get_db)):
    conversation = _conversation_or_404(db, conversation_id, _user_id(request))
    messages = db.scalars(
        select(AssistantMessage)
        .where(AssistantMessage.conversation_id == conversation.id)
        .order_by(AssistantMessage.sequence.asc())
    ).all()
    return AssistantConversationDetail(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=messages,
    )


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    conversation = _conversation_or_404(db, conversation_id, _user_id(request))
    db.delete(conversation)
    db.commit()
    return Response(status_code=204)


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, request: Request, db: Session = Depends(get_db)) -> ChatResponse:
    user_id = _user_id(request)
    business_id = getattr(request.state, "business_id", "unknown-business")
    _chat_by_ip.check(f"assistant-chat:{business_id}:{user_id}:{client_ip(request)}")

    if payload.conversation_id:
        conversation = _conversation_or_404(db, payload.conversation_id, user_id)
        recent_desc = db.scalars(
            select(AssistantMessage)
            .where(AssistantMessage.conversation_id == conversation.id)
            .order_by(AssistantMessage.sequence.desc())
            .limit(_HISTORY_LIMIT)
        ).all()
        recent = list(reversed(recent_desc))
        next_sequence = recent[-1].sequence + 1 if recent else 1
    else:
        conversation = AssistantConversation(user_id=user_id, title=_title_from_message(payload.message))
        db.add(conversation)
        db.flush()
        recent = []
        next_sequence = 1

    history = [{"role": message.role, "content": message.content} for message in recent]
    settings = get_settings()
    try:
        reply = answer_question(settings, db, payload.message, history)
    except (AssistantConfigError, AssistantProviderError) as exc:
        db.rollback()
        raise HTTPException(
            status_code=503, detail="Could not get an answer right now. Please try again."
        ) from exc

    now = datetime.utcnow()
    db.add_all(
        [
            AssistantMessage(
                conversation_id=conversation.id,
                sequence=next_sequence,
                role="user",
                content=payload.message,
                created_at=now,
            ),
            AssistantMessage(
                conversation_id=conversation.id,
                sequence=next_sequence + 1,
                role="assistant",
                content=reply,
                created_at=now,
            ),
        ]
    )
    conversation.updated_at = now
    db.commit()
    return ChatResponse(reply=reply, conversation_id=conversation.id)
