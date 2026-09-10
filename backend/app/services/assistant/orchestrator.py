"""Runs a bounded OpenAI tool-calling conversation turn over the read-only
assistant tools (see tools.py). The model never sees the database schema or
writes any query itself — it only ever picks from the fixed TOOL_DEFINITIONS
list, and every tool call is dispatched through TOOL_FUNCTIONS, the same
lookup table the model's own tool definitions were generated from."""

import json
import logging

from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.services.assistant.exceptions import AssistantConfigError, AssistantProviderError
from app.services.assistant.tools import TOOL_DEFINITIONS, TOOL_FUNCTIONS

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a helpful assistant for a small business owner using Sydney Transaction Management, an "
    "expense/sales tracking app. Answer questions about their sales/expense data "
    "using only the provided tools — never invent a number. If a tool returns no "
    "data for the question asked, say so honestly rather than guessing. Reply in "
    "the same language the user asked in (Hebrew or English). Keep answers concise "
    "and conversational, formatted for a chat bubble, not a report."
)

_MAX_TOOL_ROUNDS = 5

_TRANSIENT_TIMEOUT_ERRORS = (APITimeoutError,)
_TRANSIENT_RETRYABLE_ERRORS = (APIConnectionError, RateLimitError, InternalServerError)
_NON_TRANSIENT_ERRORS = (BadRequestError, AuthenticationError, PermissionDeniedError, NotFoundError)


def answer_question(
    settings: Settings,
    db: Session,
    message: str,
    history: list[dict[str, str]],
    client: OpenAI | None = None,
) -> str:
    if not settings.openai_api_key:
        raise AssistantConfigError("OPENAI_API_KEY is not configured.")
    if client is None:
        client = OpenAI(api_key=settings.openai_api_key, max_retries=0)

    messages: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": message})

    for _round in range(_MAX_TOOL_ROUNDS):
        message_out = _create_completion(client, settings, messages, with_tools=True)

        if not message_out.tool_calls:
            return message_out.content or ""

        messages.append(_assistant_message_dict(message_out))
        for tool_call in message_out.tool_calls:
            result = _run_tool(db, tool_call.function.name, tool_call.function.arguments)
            messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(result)})

    # Hard cap reached: ask once more without tools, forcing a text answer
    # from whatever's already been gathered, rather than looping forever.
    final = _create_completion(client, settings, messages, with_tools=False)
    return final.content or "לא הצלחתי למצוא תשובה מלאה לשאלה הזו."


def _assistant_message_dict(message) -> dict:
    return {
        "role": "assistant",
        "content": message.content,
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in message.tool_calls
        ]
        if message.tool_calls
        else None,
    }


def _create_completion(client: OpenAI, settings: Settings, messages: list[dict], *, with_tools: bool):
    try:
        response = client.chat.completions.create(
            model=settings.openai_assistant_model,
            messages=messages,
            tools=TOOL_DEFINITIONS if with_tools else None,
            timeout=settings.openai_timeout_seconds,
        )
        return response.choices[0].message
    except _TRANSIENT_TIMEOUT_ERRORS as exc:
        raise AssistantProviderError("Assistant request timed out.") from exc
    except _TRANSIENT_RETRYABLE_ERRORS as exc:
        raise AssistantProviderError(f"Assistant provider failed: {type(exc).__name__}") from exc
    except _NON_TRANSIENT_ERRORS as exc:
        raise AssistantProviderError(f"Assistant provider error: {type(exc).__name__}") from exc


def _run_tool(db: Session, name: str, arguments_json: str) -> dict:
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return {"error": f"unknown tool: {name}"}
    try:
        kwargs = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError:
        return {"error": "invalid tool arguments"}
    try:
        return func(db, **kwargs)
    except Exception as exc:  # noqa: BLE001 - a tool error must reach the model as data, not crash the request
        logger.info("assistant_tool_error tool=%s error_category=%s", name, type(exc).__name__)
        return {"error": f"tool failed: {type(exc).__name__}"}
