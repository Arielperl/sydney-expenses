from unittest.mock import patch

from app.core.config import get_settings
from app.services.assistant.exceptions import AssistantConfigError, AssistantProviderError

CHAT_URL = "/api/assistant/chat"


def test_chat_returns_reply(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    get_settings.cache_clear()
    try:
        with patch("app.api.routes.assistant.answer_question", return_value="You sold 100 ILS this month.") as mocked:
            response = client.post(CHAT_URL, json={"message": "how much this month?", "history": []})
        assert response.status_code == 200
        assert response.json() == {"reply": "You sold 100 ILS this month."}
        mocked.assert_called_once()
    finally:
        get_settings.cache_clear()


def test_chat_forwards_history(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    get_settings.cache_clear()
    try:
        with patch("app.api.routes.assistant.answer_question", return_value="ok") as mocked:
            client.post(
                CHAT_URL,
                json={
                    "message": "follow up",
                    "history": [{"role": "user", "content": "earlier"}, {"role": "assistant", "content": "answer"}],
                },
            )
        _settings, _db, _message, history = mocked.call_args[0]
        assert history == [{"role": "user", "content": "earlier"}, {"role": "assistant", "content": "answer"}]
    finally:
        get_settings.cache_clear()


def test_chat_missing_config_returns_503(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    try:
        with patch("app.api.routes.assistant.answer_question", side_effect=AssistantConfigError("no key")):
            response = client.post(CHAT_URL, json={"message": "hi", "history": []})
        assert response.status_code == 503
    finally:
        get_settings.cache_clear()


def test_chat_provider_error_returns_503(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    get_settings.cache_clear()
    try:
        with patch("app.api.routes.assistant.answer_question", side_effect=AssistantProviderError("timed out")):
            response = client.post(CHAT_URL, json={"message": "hi", "history": []})
        assert response.status_code == 503
        # The raw provider exception text must never leak to the client.
        assert "timed out" not in response.text
    finally:
        get_settings.cache_clear()


def test_chat_empty_message_is_rejected(client):
    response = client.post(CHAT_URL, json={"message": "", "history": []})
    assert response.status_code == 422
