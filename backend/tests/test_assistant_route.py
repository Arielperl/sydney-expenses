from unittest.mock import patch

import pytest

from app.api.routes import auth
from app.core.config import get_settings
from app.database import SessionLocal
from app.models.business import Business, BusinessMember
from app.services.assistant.exceptions import AssistantConfigError, AssistantProviderError

CHAT_URL = "/api/assistant/chat"
CONVERSATIONS_URL = "/api/assistant/conversations"


def _create_conversation(client, message: str = "temporary") -> str:
    with patch("app.api.routes.assistant.answer_question", return_value="ok"):
        created = client.post(CHAT_URL, json={"message": message})
    return created.json()["conversation_id"]


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


def test_conversation_can_be_renamed(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    get_settings.cache_clear()
    try:
        conversation_id = _create_conversation(client)
        url = f"{CONVERSATIONS_URL}/{conversation_id}"

        response = client.patch(url, json={"title": "התקציב הרבעוני"})

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == conversation_id
        assert body["title"] == "התקציב הרבעוני"

        # The new title persists for a fresh GET, not just the PATCH response.
        assert client.get(url).json()["title"] == "התקציב הרבעוני"
    finally:
        get_settings.cache_clear()


def test_rename_trims_surrounding_whitespace(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    get_settings.cache_clear()
    try:
        conversation_id = _create_conversation(client)
        response = client.patch(
            f"{CONVERSATIONS_URL}/{conversation_id}", json={"title": "   שם עם רווחים   "}
        )
        assert response.status_code == 200
        assert response.json()["title"] == "שם עם רווחים"
    finally:
        get_settings.cache_clear()


def test_rename_rejects_empty_title(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    get_settings.cache_clear()
    try:
        conversation_id = _create_conversation(client)
        response = client.patch(f"{CONVERSATIONS_URL}/{conversation_id}", json={"title": ""})
        assert response.status_code == 422
    finally:
        get_settings.cache_clear()


def test_rename_rejects_whitespace_only_title(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    get_settings.cache_clear()
    try:
        conversation_id = _create_conversation(client)
        response = client.patch(f"{CONVERSATIONS_URL}/{conversation_id}", json={"title": "   \t  "})
        assert response.status_code == 422
    finally:
        get_settings.cache_clear()


def test_rename_rejects_title_over_80_characters(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    get_settings.cache_clear()
    try:
        conversation_id = _create_conversation(client)
        response = client.patch(f"{CONVERSATIONS_URL}/{conversation_id}", json={"title": "א" * 81})
        assert response.status_code == 422

        # Exactly 80 (the documented limit) is accepted.
        ok = client.patch(f"{CONVERSATIONS_URL}/{conversation_id}", json={"title": "א" * 80})
        assert ok.status_code == 200
    finally:
        get_settings.cache_clear()


def test_rename_rejects_unexpected_fields(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    get_settings.cache_clear()
    try:
        conversation_id = _create_conversation(client)
        response = client.patch(
            f"{CONVERSATIONS_URL}/{conversation_id}",
            json={"title": "שם חדש", "user_id": "someone-else"},
        )
        assert response.status_code == 422
    finally:
        get_settings.cache_clear()


def test_rename_unknown_conversation_returns_404(client):
    response = client.patch(
        f"{CONVERSATIONS_URL}/00000000-0000-4000-8000-000000000099", json={"title": "שם חדש"}
    )
    assert response.status_code == 404


def test_rename_does_not_change_messages(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    get_settings.cache_clear()
    try:
        conversation_id = _create_conversation(client, message="השאלה המקורית")
        url = f"{CONVERSATIONS_URL}/{conversation_id}"
        before = client.get(url).json()["messages"]

        client.patch(url, json={"title": "כותרת חדשה"})

        after = client.get(url).json()["messages"]
        assert after == before
    finally:
        get_settings.cache_clear()


@pytest.fixture
def secured_businesses(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "cors_allowed_origins", ["http://localhost:5174"])
    with SessionLocal() as db:
        db.add_all([Business(id="business-a", name="Business A"), Business(id="business-b", name="Business B")])
        db.flush()
        db.add_all(
            [
                BusinessMember(business_id="business-a", user_id="owner-a", role="owner"),
                BusinessMember(business_id="business-a", user_id="manager-a", role="manager"),
                BusinessMember(business_id="business-a", user_id="viewer-a", role="viewer"),
                BusinessMember(business_id="business-b", user_id="owner-b", role="owner"),
            ]
        )
        db.commit()

    async def fake_auth(method, path, payload=None, token=None):
        return {"id": token, "email": f"{token}@example.com", "email_confirmed_at": "yes", "user_metadata": {}}

    monkeypatch.setattr(auth, "auth_request", fake_auth)


def _authed_create_conversation(client, user: str, message: str = "temporary") -> str:
    client.cookies.set("sydney_access", user)
    with patch("app.api.routes.assistant.answer_question", return_value="ok"):
        created = client.post(CHAT_URL, json={"message": message}, headers={"origin": "http://localhost:5174"})
    assert created.status_code == 200, created.text
    return created.json()["conversation_id"]


def test_rename_another_users_conversation_returns_404(client, secured_businesses):
    # answer_question is mocked, so no real OPENAI_API_KEY/get_settings.cache_clear()
    # dance is needed here — and clearing the settings cache would discard the
    # auth_required=True mutation secured_businesses just made on it.
    conversation_id = _authed_create_conversation(client, "owner-a")

    client.cookies.set("sydney_access", "manager-a")
    response = client.patch(
        f"{CONVERSATIONS_URL}/{conversation_id}",
        json={"title": "גניבת שיחה"},
        headers={"origin": "http://localhost:5174"},
    )
    assert response.status_code == 404


def test_rename_another_businesss_conversation_returns_404(client, secured_businesses):
    conversation_id = _authed_create_conversation(client, "owner-a")

    client.cookies.set("sydney_access", "owner-b")
    response = client.patch(
        f"{CONVERSATIONS_URL}/{conversation_id}",
        json={"title": "גניבת שיחה"},
        headers={"origin": "http://localhost:5174"},
    )
    assert response.status_code == 404


def test_viewer_cannot_rename_a_conversation(client, secured_businesses):
    conversation_id = _authed_create_conversation(client, "viewer-a")

    response = client.patch(
        f"{CONVERSATIONS_URL}/{conversation_id}",
        json={"title": "לא אמור לעבוד"},
        headers={"origin": "http://localhost:5174"},
    )
    assert response.status_code == 403

    # The title was never touched.
    get = client.get(f"{CONVERSATIONS_URL}/{conversation_id}")
    assert get.json()["title"] != "לא אמור לעבוד"
