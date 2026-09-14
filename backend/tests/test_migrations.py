"""Verifies the actual Alembic migration chain — not just the ORM models —
against a fresh, empty database. The rest of the test suite creates its
schema via `Base.metadata.create_all()`, which would never catch a bug in
the migrations themselves (e.g. a raw-SQL data backfill writing a value in
the wrong case for how SQLAlchemy's Enum type actually stores it — a real
bug this test now guards against; see a4b5c6d7e8f9's fix)."""

import tempfile
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _alembic_config() -> Config:
    # alembic/env.py reads the DB URL from get_settings(), not from
    # anything passed here — the env var + cache-clear below is what
    # actually points it at the fresh temp database, not this Config.
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return config


@pytest.fixture
def fresh_sqlite_db(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "migration_test.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
        get_settings.cache_clear()
        try:
            yield db_path
        finally:
            get_settings.cache_clear()


def test_full_migration_chain_applies_cleanly_to_an_empty_database(fresh_sqlite_db):
    config = _alembic_config()
    command.upgrade(config, "head")  # must not raise

    engine = create_engine(f"sqlite:///{fresh_sqlite_db}")
    with engine.connect() as conn:
        tables = {
            row[0]
            for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        }
    assert {
        "businesses",
        "business_members",
        "integration_connections",
        "assistant_conversations",
        "assistant_messages",
        "sales",
        "sale_events",
        "import_batches",
        "alembic_version",
    } <= tables


def test_legacy_sale_predating_tax_treatment_is_classified_and_readable_afterwards(fresh_sqlite_db):
    """Regression test for a real bug: the tax_treatment backfill migration
    wrote the enum's lowercase `.value` ('standard') directly via raw SQL,
    but SQLAlchemy's Enum(..., native_enum=False) type stores/reads a
    Python enum's member *name* ('STANDARD') by default — the same
    convention every other enum column on this table already follows when
    written through the ORM. The mismatch didn't fail the migration itself;
    it failed the next time anything read that row through the ORM
    (`LookupError: 'standard' is not among the defined enum values`)."""
    config = _alembic_config()
    command.upgrade(config, "d3e4f5a6b7c8")  # the sales table, before tax_treatment existed

    engine = create_engine(f"sqlite:///{fresh_sqlite_db}")
    with engine.connect() as conn:
        # Enum values are the member NAME ('WEBHOOK'/'SUCCEEDED'/'ISSUED'),
        # matching how SQLAlchemy's Enum(..., native_enum=False) type
        # actually stores these columns when written through the ORM —
        # exactly what a real pre-existing legacy row would contain.
        conn.execute(
            text(
                """
                INSERT INTO sales (
                    id, source, status, occurred_at, customer_name, service_name,
                    gross_amount, vat_amount, net_amount, currency,
                    document_status, created_at, updated_at
                ) VALUES (
                    'legacy-1', 'WEBHOOK', 'SUCCEEDED', '2026-01-01 00:00:00',
                    'Legacy Customer', 'Legacy Service',
                    118.00, 18.00, 100.00, 'ILS',
                    'ISSUED', '2026-01-01 00:00:00', '2026-01-01 00:00:00'
                )
                """
            )
        )
        conn.commit()

    command.upgrade(config, "head")

    from app.models.sale import Sale  # imported after upgrade so column exists

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        sale = session.get(Sale, "legacy-1")  # must not raise LookupError
        assert sale.tax_treatment.value == "standard"
        assert sale.tax_treatment_needs_review is False
        assert sale.business_id == "00000000-0000-4000-8000-000000000001"
    finally:
        session.close()
