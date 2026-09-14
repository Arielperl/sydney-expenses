"""Regression tests for the general security-hardening pass: response
headers, API docs exposure, and production-configuration fail-fast checks.
"""

import pytest

from app.core.config import InsecureProductionConfigurationError, Settings, validate_auth_settings


class TestSecurityHeaders:
    def test_api_root_redirects_to_the_configured_frontend(self, client):
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == Settings().cors_allowed_origins[0]

    def test_baseline_headers_present_on_every_response(self, client):
        response = client.get("/api/health")
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Content-Security-Policy"] == "frame-ancestors 'none'"
        assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=(), payment=()"
        assert response.headers["Cross-Origin-Opener-Policy"] == "same-origin"
        assert response.headers["X-Permitted-Cross-Domain-Policies"] == "none"

    def test_untrusted_host_is_rejected(self, client):
        response = client.get("/api/health", headers={"host": "evil.example"})
        assert response.status_code == 400

    def test_headers_present_even_on_an_auth_rejected_response(self, client, monkeypatch):
        from app.core.config import get_settings

        s = get_settings()
        monkeypatch.setattr(s, "auth_required", True)
        # protect_workspace short-circuits this with an early 401 before the
        # route ever runs — the headers must still be applied to it, not
        # only to responses that reach a route handler.
        response = client.get("/api/sales")
        assert response.status_code == 401
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"

    def test_hsts_absent_in_development(self, client):
        response = client.get("/api/health")
        assert "Strict-Transport-Security" not in response.headers


class TestApiDocsExposure:
    def test_docs_enabled_in_development(self, client):
        assert client.get("/docs").status_code == 200
        assert client.get("/openapi.json").status_code == 200

    def test_docs_and_hsts_when_app_built_in_production_mode(self, monkeypatch):
        # docs_url/openapi_url/HSTS are all decided once at app-construction
        # time (not re-evaluated per-request), so this rebuilds the app
        # under a fully valid production configuration rather than
        # monkeypatching settings after the fact.
        import importlib

        monkeypatch.setenv("APP_ENVIRONMENT", "production")
        monkeypatch.setenv("AUTH_REQUIRED", "true")
        monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
        monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_x")
        monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["https://app.example.com"]')
        monkeypatch.setenv("ALLOWED_HOSTS", '["api.example.com"]')
        monkeypatch.setenv("CSV_PREVIEW_SIGNING_SECRET", "test-only-secret-with-at-least-32-characters")
        monkeypatch.setenv("CONNECTION_SIGNING_SECRET", "test-only-connection-key-at-least-32-characters")
        monkeypatch.setenv("DOCUMENT_PROVIDER", "disabled")
        monkeypatch.setenv("RECEIPT_EXTRACTOR_PROVIDER", "openai")
        from app.core.config import get_settings

        get_settings.cache_clear()
        try:
            from fastapi.testclient import TestClient

            main_module = importlib.import_module("app.main")
            importlib.reload(main_module)
            with TestClient(main_module.app, base_url="https://api.example.com") as prod_client:
                assert prod_client.get("/docs").status_code == 404
                assert prod_client.get("/redoc").status_code == 404
                assert prod_client.get("/openapi.json").status_code == 404
                response = prod_client.get("/api/health")
                assert response.headers["Strict-Transport-Security"] == "max-age=63072000; includeSubDomains"
        finally:
            get_settings.cache_clear()
            monkeypatch.setenv("APP_ENVIRONMENT", "development")
            get_settings.cache_clear()
            importlib.reload(importlib.import_module("app.main"))
            get_settings.cache_clear()


class TestProductionConfigValidation:
    def _base_secure_settings(self, **overrides) -> Settings:
        base = dict(
            app_environment="production",
            auth_required=True,
            supabase_url="https://project.supabase.co",
            supabase_secret_key="sb_secret_x",
            cors_allowed_origins=["https://app.example.com"],
            allowed_hosts=["api.example.com"],
            csv_preview_signing_secret="test-only-secret-with-at-least-32-characters",
            connection_signing_secret="test-only-connection-key-at-least-32-characters",
            document_provider="disabled",
            receipt_extractor_provider="openai",
        )
        base.update(overrides)
        return Settings(**base)

    def test_secure_production_config_passes(self):
        validate_auth_settings(self._base_secure_settings())  # must not raise

    def test_development_config_is_never_validated(self):
        settings = Settings(app_environment="development", auth_required=False, cors_allowed_origins=["http://localhost:5173"])
        validate_auth_settings(settings)  # must not raise regardless of content

    @pytest.mark.parametrize(
        "overrides",
        [
            {"auth_required": False},
            {"supabase_url": None},
            {"supabase_secret_key": None},
            {"cors_allowed_origins": ["http://localhost:5173"]},
            {"cors_allowed_origins": ["http://app.example.com"]},
            {"allowed_hosts": ["*"]},
            {"allowed_hosts": ["localhost"]},
            {"csv_preview_signing_secret": "short"},
            {"connection_signing_secret": "short"},
            {"document_provider": "mock"},
            {"receipt_extractor_provider": "mock"},
            {"supabase_url": "http://project.supabase.co"},
        ],
    )
    def test_insecure_production_config_fails_fast(self, overrides):
        settings = self._base_secure_settings(**overrides)
        with pytest.raises(InsecureProductionConfigurationError):
            validate_auth_settings(settings)
