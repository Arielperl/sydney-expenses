"""Migration tests for the payment foundation tables.

Always run against a fresh temporary SQLite database. When
PAYMENTS_TEST_POSTGRES_URL points at a disposable PostgreSQL database, the
same checks also run there (triggers, partial index and RLS are
dialect-specific). Never point it at a shared or live database: the test
downgrades the schema.
"""

import os
import tempfile
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

from app.core.config import get_settings

BACKEND_DIR = Path(__file__).resolve().parent.parent
PAYMENT_REVISION = "f6a7b8c9d0e1"
PREVIOUS_REVISION = "e5f6a7b8c9d0"
PAYMENT_TABLES = {"payment_intents", "payment_refunds", "payment_webhook_events", "payment_audit_events"}
EXISTING_TABLES = {"businesses", "sales", "webhook_events", "integration_connections", "support_requests", "support_messages"}


def _config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return config


def _database_urls():
    urls = ["sqlite"]
    if os.environ.get("PAYMENTS_TEST_POSTGRES_URL"):
        urls.append("postgresql")
    return urls


@pytest.fixture(params=_database_urls())
def migration_db(request, monkeypatch):
    if request.param == "postgresql":
        url = os.environ["PAYMENTS_TEST_POSTGRES_URL"]
        assert "localhost" in url or "127.0.0.1" in url, "Only a local, disposable PostgreSQL may be used"
        monkeypatch.setenv("DATABASE_URL", url)
        get_settings.cache_clear()
        yield url
        engine = create_engine(url)
        with engine.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
        engine.dispose()
        get_settings.cache_clear()
        return
    with tempfile.TemporaryDirectory() as tmp_dir:
        url = f"sqlite:///{Path(tmp_dir) / 'payments_migration.db'}"
        monkeypatch.setenv("DATABASE_URL", url)
        get_settings.cache_clear()
        yield url
        get_settings.cache_clear()


def _tables(url):
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def _seed_intent(conn, business_id: str) -> tuple[str, str]:
    conn.execute(text("INSERT INTO businesses (id, name, country_code, currency, timezone, vat_rate, created_at) "
                      "VALUES (:id, 'Migration test', 'IL', 'ILS', 'Asia/Jerusalem', 0.18, CURRENT_TIMESTAMP)"), {"id": business_id})
    intent_id = str(uuid.uuid4())
    conn.execute(text(
        "INSERT INTO payment_intents (id, business_id, external_reference, provider, amount_minor, currency, description, "
        "idempotency_key, request_fingerprint, status) VALUES (:id, :b, 'ref-1', 'fake', 1000, 'ILS', 'x', 'key-00001', 'f', 'created')"
    ), {"id": intent_id, "b": business_id})
    audit_id = str(uuid.uuid4())
    conn.execute(text(
        "INSERT INTO payment_audit_events (id, business_id, payment_intent_id, sequence, entity, to_status, source) "
        "VALUES (:id, :b, :i, 1, 'payment', 'created', 'api')"
    ), {"id": audit_id, "b": business_id, "i": intent_id})
    return intent_id, audit_id


def test_payment_migration_upgrades_downgrades_and_upgrades_again(migration_db):
    config = _config()
    command.upgrade(config, PREVIOUS_REVISION)
    before = _tables(migration_db)
    assert EXISTING_TABLES <= before and not (PAYMENT_TABLES & before)

    command.upgrade(config, "head")
    assert PAYMENT_TABLES <= _tables(migration_db)

    command.downgrade(config, PREVIOUS_REVISION)
    after_downgrade = _tables(migration_db)
    assert not (PAYMENT_TABLES & after_downgrade)
    assert after_downgrade == before  # nothing else was touched

    command.upgrade(config, "head")
    assert PAYMENT_TABLES <= _tables(migration_db)


def test_migrated_schema_enforces_money_and_uniqueness_rules(migration_db):
    command.upgrade(_config(), "head")
    engine = create_engine(migration_db)
    business_id = str(uuid.uuid4())
    try:
        with engine.begin() as conn:
            intent_id, _ = _seed_intent(conn, business_id)

        bad_statements = [
            "UPDATE payment_intents SET status = 'teleported' WHERE id = :i",
            "UPDATE payment_intents SET captured_minor = 1001 WHERE id = :i",
            "UPDATE payment_intents SET refund_reserved_minor = 1 WHERE id = :i",
            "UPDATE payment_intents SET currency = 'ils' WHERE id = :i",
            "UPDATE payment_intents SET checkout_url = 'http://insecure.test' WHERE id = :i",
            # A second live intent for the same external reference.
            "INSERT INTO payment_intents (id, business_id, external_reference, provider, amount_minor, currency, description, "
            "idempotency_key, request_fingerprint, status) VALUES ('dup', :b, 'ref-1', 'fake', 5, 'ILS', 'x', 'key-00002', 'f', 'pending')",
            # The same idempotency key twice in one business.
            "INSERT INTO payment_intents (id, business_id, external_reference, provider, amount_minor, currency, description, "
            "idempotency_key, request_fingerprint, status) VALUES ('dup2', :b, 'ref-2', 'fake', 5, 'ILS', 'x', 'key-00001', 'f', 'created')",
        ]
        for statement in bad_statements:
            with pytest.raises(DBAPIError):
                with engine.begin() as conn:
                    conn.execute(text(statement), {"i": intent_id, "b": business_id})

        # Once the first attempt is cancelled, the reference may be used again.
        with engine.begin() as conn:
            conn.execute(text("UPDATE payment_intents SET status = 'cancelled' WHERE id = :i"), {"i": intent_id})
            conn.execute(text(
                "INSERT INTO payment_intents (id, business_id, external_reference, provider, amount_minor, currency, description, "
                "idempotency_key, request_fingerprint, status) VALUES ('retry', :b, 'ref-1', 'fake', 5, 'ILS', 'x', 'key-00003', 'f', 'created')"
            ), {"b": business_id})
    finally:
        engine.dispose()


def test_migrated_audit_table_is_append_only(migration_db):
    command.upgrade(_config(), "head")
    engine = create_engine(migration_db)
    try:
        with engine.begin() as conn:
            _, audit_id = _seed_intent(conn, str(uuid.uuid4()))
        for statement in ("UPDATE payment_audit_events SET note = 'x' WHERE id = :a", "DELETE FROM payment_audit_events WHERE id = :a"):
            with pytest.raises(DBAPIError) as error:
                with engine.begin() as conn:
                    conn.execute(text(statement), {"a": audit_id})
            assert "append-only" in str(error.value)
    finally:
        engine.dispose()


def test_row_level_security_is_enabled_on_postgres(migration_db):
    if not migration_db.startswith("postgresql"):
        pytest.skip("RLS is PostgreSQL-only")
    command.upgrade(_config(), "head")
    engine = create_engine(migration_db)
    try:
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT relname, relrowsecurity FROM pg_class WHERE relname = ANY(:names)"), {"names": list(PAYMENT_TABLES)})
            enabled = {name: flag for name, flag in result}
        assert enabled == {name: True for name in PAYMENT_TABLES}
    finally:
        engine.dispose()
