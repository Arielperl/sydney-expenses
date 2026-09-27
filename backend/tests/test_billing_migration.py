"""The subscription-billing migration on a database that already has real
businesses, members, connections and sales — the path production will take.

Runs on a temporary SQLite database, and also on PostgreSQL when
BILLING_TEST_POSTGRES_URL points at a local, disposable database.
"""

import os
import tempfile
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import DBAPIError

from app.billing.plans import PLANS
from app.billing.service import identity_hash
from app.core.config import get_settings

BACKEND_DIR = Path(__file__).resolve().parent.parent
BEFORE_BILLING = "e5f6a7b8c9d0"
BILLING = "d7e8f9a0b1c2"
LEGACY = "00000000-0000-4000-8000-000000000001"
BILLING_TABLES = {"subscription_plans", "subscription_plan_prices", "business_subscriptions", "subscription_events",
                  "billing_checkout_sessions", "billing_webhook_events", "billing_usage_counters", "billing_trial_claims"}


def _config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return config


@pytest.fixture(params=["sqlite"] + (["postgresql"] if os.environ.get("BILLING_TEST_POSTGRES_URL") else []))
def db_url(request, monkeypatch):
    if request.param == "postgresql":
        url = os.environ["BILLING_TEST_POSTGRES_URL"]
        assert "localhost" in url or "127.0.0.1" in url, "Only a local, disposable PostgreSQL may be used"
        monkeypatch.setenv("DATABASE_URL", url)
        get_settings.cache_clear()
        yield url
        engine = sa.create_engine(url)
        with engine.begin() as conn:
            conn.execute(sa.text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
        engine.dispose()
        get_settings.cache_clear()
        return
    with tempfile.TemporaryDirectory() as tmp:
        url = f"sqlite:///{Path(tmp) / 'billing_migration.db'}"
        monkeypatch.setenv("DATABASE_URL", url)
        get_settings.cache_clear()
        yield url
        get_settings.cache_clear()


def _insert(conn, table: str, values: dict) -> None:
    """Insert a row, filling any other required column with a neutral value."""
    reflected = sa.Table(table, sa.MetaData(), autoload_with=conn)
    row = dict(values)
    for column in reflected.columns:
        if column.name in row or column.nullable or column.server_default is not None or column.primary_key and column.name in row:
            continue
        kind = column.type
        if isinstance(kind, sa.Boolean):
            row[column.name] = False
        elif isinstance(kind, (sa.Integer, sa.Numeric)):
            row[column.name] = 0
        elif isinstance(kind, sa.DateTime):
            row[column.name] = datetime(2026, 1, 1)
        else:
            row[column.name] = "x"
    conn.execute(reflected.insert().values(**row))


def _seed_existing_production_like_data(url: str) -> dict:
    engine = sa.create_engine(url)
    ids = {"real": str(uuid.uuid4()), "busy": str(uuid.uuid4()), "empty": str(uuid.uuid4())}
    with engine.begin() as conn:
        for key, number in (("real", "514-789-632"), ("busy", None), ("empty", None)):
            _insert(conn, "businesses", {"id": ids[key], "name": key.title(), "business_number": number,
                                          "created_at": datetime(2026, 5, 1)})
        assert conn.execute(sa.text("SELECT count(*) FROM businesses WHERE id = :id"), {"id": LEGACY}).scalar() == 1
        _insert(conn, "business_members", {"business_id": LEGACY, "user_id": "legacy-owner", "role": "owner",
                                           "created_at": datetime(2026, 1, 1)})  # even with a member, the placeholder gets no trial
        for key, user in (("real", "owner-real"), ("busy", "owner-busy")):
            _insert(conn, "business_members", {"business_id": ids[key], "user_id": user, "role": "owner",
                                                "created_at": datetime(2026, 5, 1)})
            _insert(conn, "app_accounts", {"user_id": user, "email": f"{user}@example.com", "system_role": "user",
                                            "display_name": user, "created_at": datetime(2026, 5, 1), "updated_at": datetime(2026, 5, 1)})
        for i in range(4):  # "busy" already has more connections than the Business plan allows
            _insert(conn, "integration_connections", {"id": str(uuid.uuid4()), "business_id": ids["busy"], "provider": "demo-pay",
                                                      "name": f"Till {i}", "secret_salt": "salt", "enabled": True,
                                                      "created_at": datetime(2026, 5, 1), "updated_at": datetime(2026, 5, 1)})
        for i in range(3):
            _insert(conn, "sales", {"id": f"sale-{i}", "business_id": ids["real"], "source": "MANUAL", "status": "SUCCEEDED",
                                    "document_status": "NOT_REQUIRED", "customer_name": f"Customer {i}",
                                    "service_name": "Service", "gross_amount": Decimal("118.00"), "net_amount": Decimal("100.00"),
                                    "currency": "ILS", "occurred_at": datetime(2026, 6, 1), "created_at": datetime(2026, 6, 1),
                                    "updated_at": datetime(2026, 6, 1)})
    engine.dispose()
    return ids


def _snapshot(url: str) -> dict:
    engine = sa.create_engine(url)
    with engine.connect() as conn:
        snapshot = {
            table: sorted(tuple(str(v) for v in row) for row in conn.execute(sa.text(f"SELECT * FROM {table}")))
            for table in ("businesses", "business_members", "app_accounts", "integration_connections", "sales")
        }
    engine.dispose()
    return snapshot


def test_existing_businesses_get_a_fresh_trial_and_keep_all_their_data(db_url):
    config = _config()
    command.upgrade(config, BEFORE_BILLING)
    ids = _seed_existing_production_like_data(db_url)
    before = _snapshot(db_url)
    started = datetime.utcnow().replace(microsecond=0) - timedelta(seconds=1)
    command.upgrade(config, BILLING)

    assert _snapshot(db_url) == before  # no existing row changed or disappeared
    engine = sa.create_engine(db_url)
    with engine.connect() as conn:
        subs = {row.business_id: row for row in conn.execute(sa.text("SELECT * FROM business_subscriptions"))}
        claims = {row.identity_hash for row in conn.execute(sa.text("SELECT identity_hash FROM billing_trial_claims"))}
        events = conn.execute(sa.text("SELECT event_type, source FROM subscription_events")).fetchall()
        prices = {(r.plan_code, r.interval): r.amount_minor for r in conn.execute(sa.text("SELECT * FROM subscription_plan_prices"))}
    engine.dispose()

    assert set(subs) == {ids["real"], ids["busy"]}  # no trial for the legacy placeholder or a business without members
    real, busy = subs[ids["real"]], subs[ids["busy"]]
    assert real.status == "trialing" and real.plan_code == "business"
    assert busy.plan_code == "pro"  # 4 connections: never placed over its limit
    trial_start = real.trial_started_at if isinstance(real.trial_started_at, datetime) else datetime.fromisoformat(str(real.trial_started_at))
    trial_end = real.trial_ends_at if isinstance(real.trial_ends_at, datetime) else datetime.fromisoformat(str(real.trial_ends_at))
    assert started <= trial_start <= datetime.utcnow() and trial_end - trial_start == timedelta(days=30)
    assert identity_hash("email", "owner-real@example.com") in claims
    assert identity_hash("business_number", "514789632") in claims
    assert sorted(events) == [("trial_granted_on_migration", "system")] * 2
    assert prices == {(p.code, i): (p.monthly_price_minor if i == "month" else p.yearly_price_minor)
                      for p in PLANS for i in ("month", "year")}


def test_billing_migration_downgrades_and_upgrades_cleanly(db_url):
    config = _config()
    command.upgrade(config, BEFORE_BILLING)
    _seed_existing_production_like_data(db_url)
    before = _snapshot(db_url)
    command.upgrade(config, "head")
    command.downgrade(config, BEFORE_BILLING)
    engine = sa.create_engine(db_url)
    tables = set(sa.inspect(engine).get_table_names())
    engine.dispose()
    assert not (BILLING_TABLES & tables)
    assert _snapshot(db_url) == before
    command.upgrade(config, "head")


def test_migrated_subscription_history_is_append_only_and_constrained(db_url):
    config = _config()
    command.upgrade(config, BEFORE_BILLING)
    ids = _seed_existing_production_like_data(db_url)
    command.upgrade(config, BILLING)
    engine = sa.create_engine(db_url)
    try:
        for statement in ("UPDATE subscription_events SET reason = 'x'", "DELETE FROM subscription_events"):
            with pytest.raises(DBAPIError) as error:
                with engine.begin() as conn:
                    conn.execute(sa.text(statement))
            assert "append-only" in str(error.value)
        bad = [
            ("UPDATE business_subscriptions SET status = 'free_forever' WHERE business_id = :b", {"b": ids["real"]}),
            ("UPDATE business_subscriptions SET trial_ends_at = trial_started_at WHERE business_id = :b", {"b": ids["real"]}),
            ("INSERT INTO business_subscriptions (id, business_id, plan_code, billing_interval, status, trial_started_at, "
             "trial_ends_at, created_at, updated_at) VALUES ('dup', :b, 'starter', 'month', 'trialing', :n, :e, :n, :n)",
             {"b": ids["real"], "n": datetime(2026, 9, 1), "e": datetime(2026, 10, 1)}),
            ("INSERT INTO subscription_events (id, business_id, subscription_id, sequence, event_type, source, details) "
             "SELECT 'x', business_id, id, 99, 'forged', 'admin', '{}' FROM business_subscriptions WHERE business_id = :b",
             {"b": ids["real"]}),
        ]
        for statement, params in bad:
            with pytest.raises(DBAPIError):
                with engine.begin() as conn:
                    conn.execute(sa.text(statement), params)
    finally:
        engine.dispose()


def test_rls_is_enabled_on_billing_tables_in_postgres(db_url):
    if not db_url.startswith("postgresql"):
        pytest.skip("RLS is PostgreSQL-only")
    command.upgrade(_config(), BILLING)
    engine = sa.create_engine(db_url)
    with engine.connect() as conn:
        rows = conn.execute(sa.text("SELECT relname, relrowsecurity FROM pg_class WHERE relname = ANY(:t)"),
                            {"t": list(BILLING_TABLES)})
        enabled = {name: flag for name, flag in rows}
    engine.dispose()
    assert enabled == {table: True for table in BILLING_TABLES}
