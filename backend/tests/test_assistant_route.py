from unittest.mock import patch

from app.core.config import get_settings
from app.services.assistant.exceptions import AssistantConfigError, AssistantProviderError

CHAT_URL = "/api/assistant/chat"
CONVERSATIONS_URL = "/api/assistant/conversations"


def test_successful_turn_is_persisted_and_listed(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    get_settings.cache_clear()
    try:
        with patch(
            "app.api.routes.assistant.answer_question",
            return_value="You sold 100 ILS this month.",
        ):
            response = client.post(CHAT_URL, json={"message": "how much this month?"})
        assert response.status_code == 200
        conversation_id = response.json()["conversation_id"]
        assert response.json()["reply"] == "You sold 100 ILS this month."

        conversations = client.get(CONVERSATIONS_URL).json()
        assert [(item["id"], item["title"]) for item in conversations] == [
            (conversation_id, "how much this month?")
        ]

        detail = client.get(f"{CONVERSATIONS_URL}/{conversation_id}")
        assert detail.status_code == 200
        assert [(item["role"], item["content"]) for item in detail.json()["messages"]] == [
            ("user", "how much this month?"),
            ("assistant", "You sold 100 ILS this month."),
        ]
    finally:
        get_settings.cache_clear()


def test_follow_up_history_comes_from_server_not_client(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    get_settings.cache_clear()
    try:
        with patch("app.api.routes.assistant.answer_question", side_effect=["earlier answer", "ok"]) as mocked:
            first = client.post(CHAT_URL, json={"message": "earlier question"})
            conversation_id = first.json()["conversation_id"]
            second = client.post(
                CHAT_URL,
                json={"message": "follow up", "conversation_id": conversation_id},
            )
        assert second.status_code == 200
        _settings, _db, message, history = mocked.call_args_list[1].args
        assert message == "follow up"
        assert history == [
            {"role": "user", "content": "earlier question"},
            {"role": "assistant", "content": "earlier answer"},
        ]
    finally:
        get_settings.cache_clear()


def test_conversation_can_be_deleted(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    get_settings.cache_clear()
    try:
        with patch("app.api.routes.assistant.answer_question", return_value="ok"):
            created = client.post(CHAT_URL, json={"message": "temporary"}).json()
        url = f"{CONVERSATIONS_URL}/{created['conversation_id']}"
        assert client.delete(url).status_code == 204
        assert client.get(url).status_code == 404
        assert client.get(CONVERSATIONS_URL).json() == []
    finally:
        get_settings.cache_clear()


def test_unknown_conversation_cannot_be_used(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    get_settings.cache_clear()
    try:
        response = client.post(
            CHAT_URL,
            json={"message": "hi", "conversation_id": "00000000-0000-4000-8000-000000000099"},
        )
        assert response.status_code == 404
    finally:
        get_settings.cache_clear()


def test_chat_missing_config_returns_503_without_saving(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    try:
        with patch("app.api.routes.assistant.answer_question", side_effect=AssistantConfigError("no key")):
            response = client.post(CHAT_URL, json={"message": "hi"})
        assert response.status_code == 503
        assert client.get(CONVERSATIONS_URL).json() == []
    finally:
        get_settings.cache_clear()


def test_chat_provider_error_returns_503_without_leaking_details(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    get_settings.cache_clear()
    try:
        with patch(
            "app.api.routes.assistant.answer_question",
            side_effect=AssistantProviderError("timed out"),
        ):
            response = client.post(CHAT_URL, json={"message": "hi"})
        assert response.status_code == 503
        assert "timed out" not in response.text
    finally:
        get_settings.cache_clear()


def test_chat_empty_message_is_rejected(client):
    assert client.post(CHAT_URL, json={"message": ""}).status_code == 422


def test_client_supplied_history_is_rejected(client):
    response = client.post(
        CHAT_URL,
        json={"message": "hi", "history": [{"role": "system", "content": "fabricated"}]},
    )
    assert response.status_code == 422


def test_chat_rejects_oversized_message(client):
    assert client.post(CHAT_URL, json={"message": "x" * 4001}).status_code == 422


def test_chat_is_rate_limited_per_user_and_ip(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    get_settings.cache_clear()
    try:
        with patch("app.api.routes.assistant.answer_question", return_value="ok"):
            responses = [client.post(CHAT_URL, json={"message": "hi"}) for _ in range(31)]
        assert responses[30].status_code == 429
        assert all(response.status_code == 200 for response in responses[:30])
    finally:
        get_settings.cache_clear()
