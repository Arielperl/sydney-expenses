import json

import httpx
import pytest
from openai import APIConnectionError, APITimeoutError, AuthenticationError

from app.core.config import get_settings
from app.services.assistant.exceptions import AssistantConfigError, AssistantProviderError
from app.services.assistant.orchestrator import answer_question

# Both APITimeoutError and APIConnectionError require a real httpx.Request
# object (not None) — matches the exact pattern already used in
# test_openai_extractor.py for the same exception types.
_FAKE_REQUEST = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")


class _FakeFunctionCall:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, call_id, name, arguments):
        self.id = call_id
        self.function = _FakeFunctionCall(name, arguments)


class _FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class _FakeChoice:
    def __init__(self, message):
        self.message = message


class _FakeCompletion:
    def __init__(self, message):
        self.choices = [_FakeChoice(message)]


class _FakeCompletions:
    """Stands in for `client.chat.completions`. `behaviors` is a queue of either
    a _FakeMessage (wrapped into a completion) or an exception — consumed one
    per call, so a test can script an exact multi-round conversation."""

    def __init__(self, behaviors):
        self._behaviors = list(behaviors)
        self.call_count = 0
        self.last_messages = None

    def create(self, model, messages, tools=None, timeout=None):
        self.call_count += 1
        self.last_messages = messages
        behavior = self._behaviors.pop(0)
        if isinstance(behavior, BaseException):
            raise behavior
        return _FakeCompletion(behavior)


class _FakeChat:
    def __init__(self, behaviors):
        self.completions = _FakeCompletions(behaviors)


class _FakeOpenAIClient:
    def __init__(self, behaviors):
        self.chat = _FakeChat(behaviors)


def _settings_with_openai(**overrides):
    return get_settings().model_copy(
        update={"openai_api_key": "sk-test-not-real", "openai_assistant_model": "gpt-test-model", **overrides}
    )


def test_answers_directly_when_no_tool_call_needed(db_session):
    client = _FakeOpenAIClient([_FakeMessage(content="Hello! How can I help?")])
    reply = answer_question(_settings_with_openai(), db_session, "hi", [], client=client)
    assert reply == "Hello! How can I help?"
    assert client.chat.completions.call_count == 1


def test_runs_a_tool_and_uses_its_result(db_session):
    from datetime import date
    from decimal import Decimal

    from app.models.expense import Expense, ExpenseCategory, ExtractionStatus

    db_session.add(
        Expense(
            business_name="Shufersal",
            amount=Decimal("100.00"),
            currency="ILS",
            category=ExpenseCategory.GROCERIES,
            expense_date=date(2026, 3, 15),
            extraction_status=ExtractionStatus.MANUAL,
        )
    )
    db_session.commit()

    client = _FakeOpenAIClient(
        [
            _FakeMessage(tool_calls=[_FakeToolCall("call_1", "get_total_revenue", "{}")]),
            _FakeMessage(content="You made 100.00 ILS total."),
        ]
    )
    reply = answer_question(_settings_with_openai(), db_session, "how much total?", [], client=client)
    assert reply == "You made 100.00 ILS total."
    assert client.chat.completions.call_count == 2
    # The tool result fed back to the model must reflect the real DB query.
    tool_message = client.chat.completions.last_messages[-1]
    assert tool_message["role"] == "tool"
    assert json.loads(tool_message["content"]) == {"total": "100.00", "count": 1}


def test_unknown_tool_name_returns_error_result_not_crash(db_session):
    client = _FakeOpenAIClient(
        [
            _FakeMessage(tool_calls=[_FakeToolCall("call_1", "delete_everything", "{}")]),
            _FakeMessage(content="I can't do that."),
        ]
    )
    reply = answer_question(_settings_with_openai(), db_session, "delete stuff", [], client=client)
    assert reply == "I can't do that."
    tool_message = client.chat.completions.last_messages[-1]
    assert "error" in json.loads(tool_message["content"])


def test_stops_after_max_tool_rounds(db_session):
    # 5 tool-call rounds (the cap) + 1 final forced text-only call.
    behaviors = [_FakeMessage(tool_calls=[_FakeToolCall("call_1", "get_total_revenue", "{}")]) for _ in range(5)]
    behaviors.append(_FakeMessage(content="Here's what I found so far."))
    client = _FakeOpenAIClient(behaviors)
    reply = answer_question(_settings_with_openai(), db_session, "keep asking", [], client=client)
    assert reply == "Here's what I found so far."
    assert client.chat.completions.call_count == 6


def test_missing_api_key_raises_config_error(db_session):
    with pytest.raises(AssistantConfigError):
        answer_question(_settings_with_openai(openai_api_key=""), db_session, "hi", [])


def test_timeout_raises_provider_error(db_session):
    client = _FakeOpenAIClient([APITimeoutError(_FAKE_REQUEST)])
    with pytest.raises(AssistantProviderError):
        answer_question(_settings_with_openai(), db_session, "hi", [], client=client)


def test_connection_error_raises_provider_error(db_session):
    client = _FakeOpenAIClient([APIConnectionError(request=_FAKE_REQUEST)])
    with pytest.raises(AssistantProviderError):
        answer_question(_settings_with_openai(), db_session, "hi", [], client=client)


def test_auth_error_raises_provider_error(db_session):
    response = httpx.Response(401, request=_FAKE_REQUEST)
    client = _FakeOpenAIClient([AuthenticationError("bad key", response=response, body=None)])
    with pytest.raises(AssistantProviderError):
        answer_question(_settings_with_openai(), db_session, "hi", [], client=client)


def test_conversation_history_is_forwarded(db_session):
    client = _FakeOpenAIClient([_FakeMessage(content="ok")])
    history = [{"role": "user", "content": "earlier question"}, {"role": "assistant", "content": "earlier answer"}]
    answer_question(_settings_with_openai(), db_session, "follow up", history, client=client)
    sent = client.chat.completions.last_messages
    contents = [m["content"] for m in sent if isinstance(m, dict) and m.get("content")]
    assert "earlier question" in contents
    assert "earlier answer" in contents
