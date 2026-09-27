"""Add the (inactive) payment orchestration foundation tables.

Revision ID: f6a7b8c9d0e1
Revises: d7e8f9a0b1c2

Purely additive: four new tables, no change to any existing table. Nothing
in the running application reads or writes them yet (see
app/payments/__init__.py and docs/payments-foundation.md).

The downgrade drops these tables. That is only acceptable while the module is
inactive and the tables are empty; once real payments exist, the audit trail
and payment records must be retained and this downgrade must not be run.
"""

import sqlalchemy as sa
from alembic import op

revision = "f6a7b8c9d0e1"
down_revision = "d7e8f9a0b1c2"
branch_labels = None
depends_on = None

PAYMENT_STATUSES = (
    "created", "pending", "requires_action", "authorized", "captured",
    "failed", "cancelled", "partially_refunded", "refunded", "expired",
)
OCCUPYING_STATUSES = tuple(sorted(set(PAYMENT_STATUSES) - {"failed", "cancelled", "expired"}))
REFUND_STATUSES = ("pending", "succeeded", "failed")
WEBHOOK_STATUSES = ("received", "processed", "ignored", "failed")
AUDIT_SOURCES = ("api", "provider_event", "system")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} in ({', '.join(repr(value) for value in values)})"


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    ]


def upgrade() -> None:
    op.create_table(
        "payment_intents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("external_reference", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("provider_payment_id", sa.String(255), nullable=True),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("captured_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("refund_reserved_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("refunded_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("customer_reference", sa.String(64), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="created"),
        sa.Column("checkout_url", sa.String(2048), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_user_id", sa.String(128), nullable=True),
        *_timestamps(),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("business_id", "idempotency_key", name="uq_payment_intents_idempotency"),
        sa.UniqueConstraint("business_id", "provider", "provider_payment_id", name="uq_payment_intents_provider_payment"),
        sa.CheckConstraint(_in("status", PAYMENT_STATUSES), name="ck_payment_intents_status"),
        sa.CheckConstraint("amount_minor > 0 AND amount_minor <= 1000000000000", name="ck_payment_intents_amount"),
        sa.CheckConstraint("length(currency) = 3 AND upper(currency) = currency", name="ck_payment_intents_currency"),
        sa.CheckConstraint("captured_minor >= 0 AND captured_minor <= amount_minor", name="ck_payment_intents_captured"),
        sa.CheckConstraint(
            "refund_reserved_minor >= 0 AND refund_reserved_minor <= captured_minor", name="ck_payment_intents_refund_reserved"
        ),
        sa.CheckConstraint("refunded_minor >= 0 AND refunded_minor <= refund_reserved_minor", name="ck_payment_intents_refunded"),
        sa.CheckConstraint("checkout_url IS NULL OR checkout_url LIKE 'https://%'", name="ck_payment_intents_checkout_url_https"),
        sa.CheckConstraint("version >= 1", name="ck_payment_intents_version"),
    )
    op.create_index("ix_payment_intents_business_id", "payment_intents", ["business_id"])
    op.create_index("ix_payment_intents_business_created", "payment_intents", ["business_id", "created_at"])
    op.create_index(
        "uq_payment_intents_active_reference", "payment_intents", ["business_id", "external_reference"], unique=True,
        sqlite_where=sa.text(_in("status", OCCUPYING_STATUSES)),
        postgresql_where=sa.text(_in("status", OCCUPYING_STATUSES)),
    )

    op.create_table(
        "payment_refunds",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("payment_intent_id", sa.String(36), sa.ForeignKey("payment_intents.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("provider_refund_id", sa.String(255), nullable=True),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("failure_reason", sa.String(255), nullable=True),
        sa.Column("created_by_user_id", sa.String(128), nullable=True),
        *_timestamps(),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("business_id", "idempotency_key", name="uq_payment_refunds_idempotency"),
        sa.UniqueConstraint("business_id", "provider_refund_id", name="uq_payment_refunds_provider_refund"),
        sa.CheckConstraint(_in("status", REFUND_STATUSES), name="ck_payment_refunds_status"),
        sa.CheckConstraint("amount_minor > 0 AND amount_minor <= 1000000000000", name="ck_payment_refunds_amount"),
        sa.CheckConstraint("length(currency) = 3 AND upper(currency) = currency", name="ck_payment_refunds_currency"),
        sa.CheckConstraint("version >= 1", name="ck_payment_refunds_version"),
    )
    op.create_index("ix_payment_refunds_business_id", "payment_refunds", ["business_id"])
    op.create_index("ix_payment_refunds_payment_intent_id", "payment_refunds", ["payment_intent_id"])

    op.create_table(
        "payment_webhook_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("provider_event_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload_summary", sa.JSON(), nullable=False),
        sa.Column("payment_intent_id", sa.String(36), sa.ForeignKey("payment_intents.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("status", sa.String(32), nullable=False, server_default="received"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("business_id", "provider", "provider_event_id", name="uq_payment_webhook_events_provider_event"),
        sa.CheckConstraint(_in("status", WEBHOOK_STATUSES), name="ck_payment_webhook_events_status"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_payment_webhook_events_attempts"),
    )
    op.create_index("ix_payment_webhook_events_business_id", "payment_webhook_events", ["business_id"])
    op.create_index("ix_payment_webhook_events_status", "payment_webhook_events", ["business_id", "status"])

    op.create_table(
        "payment_audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("payment_intent_id", sa.String(36), sa.ForeignKey("payment_intents.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("refund_id", sa.String(36), sa.ForeignKey("payment_refunds.id", ondelete="RESTRICT"), nullable=True),
        sa.Column(
            "webhook_event_id", sa.String(36), sa.ForeignKey("payment_webhook_events.id", ondelete="RESTRICT"), nullable=True
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("entity", sa.String(16), nullable=False),
        sa.Column("from_status", sa.String(32), nullable=True),
        sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("actor_user_id", sa.String(128), nullable=True),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(_in("source", AUDIT_SOURCES), name="ck_payment_audit_events_source"),
        sa.CheckConstraint("entity in ('payment', 'refund')", name="ck_payment_audit_events_entity"),
        sa.CheckConstraint("sequence >= 1", name="ck_payment_audit_events_sequence"),
        sa.UniqueConstraint("payment_intent_id", "sequence", name="uq_payment_audit_events_sequence"),
    )
    op.create_index("ix_payment_audit_events_business_id", "payment_audit_events", ["business_id"])
    op.create_index("ix_payment_audit_events_intent_created", "payment_audit_events", ["payment_intent_id", "created_at"])

    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(sa.text(
            "CREATE FUNCTION payment_audit_events_immutable() RETURNS trigger AS $$ "
            "BEGIN RAISE EXCEPTION 'payment_audit_events is append-only'; END; $$ LANGUAGE plpgsql"
        ))
        op.execute(sa.text(
            "CREATE TRIGGER trg_payment_audit_events_immutable BEFORE UPDATE OR DELETE ON payment_audit_events "
            "FOR EACH ROW EXECUTE FUNCTION payment_audit_events_immutable()"
        ))
        for table in ("payment_intents", "payment_refunds", "payment_webhook_events", "payment_audit_events"):
            op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
    elif dialect == "sqlite":
        for action in ("UPDATE", "DELETE"):
            op.execute(sa.text(
                f"CREATE TRIGGER trg_payment_audit_events_no_{action.lower()} BEFORE {action} ON payment_audit_events "
                "BEGIN SELECT RAISE(ABORT, 'payment_audit_events is append-only'); END"
            ))


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(sa.text("DROP TRIGGER IF EXISTS trg_payment_audit_events_immutable ON payment_audit_events"))
        op.execute(sa.text("DROP FUNCTION IF EXISTS payment_audit_events_immutable()"))
    elif dialect == "sqlite":
        for action in ("update", "delete"):
            op.execute(sa.text(f"DROP TRIGGER IF EXISTS trg_payment_audit_events_no_{action}"))
    op.drop_index("ix_payment_audit_events_intent_created", table_name="payment_audit_events")
    op.drop_index("ix_payment_audit_events_business_id", table_name="payment_audit_events")
    op.drop_table("payment_audit_events")
    op.drop_index("ix_payment_webhook_events_status", table_name="payment_webhook_events")
    op.drop_index("ix_payment_webhook_events_business_id", table_name="payment_webhook_events")
    op.drop_table("payment_webhook_events")
    op.drop_index("ix_payment_refunds_payment_intent_id", table_name="payment_refunds")
    op.drop_index("ix_payment_refunds_business_id", table_name="payment_refunds")
    op.drop_table("payment_refunds")
    op.drop_index("uq_payment_intents_active_reference", table_name="payment_intents")
    op.drop_index("ix_payment_intents_business_created", table_name="payment_intents")
    op.drop_index("ix_payment_intents_business_id", table_name="payment_intents")
    op.drop_table("payment_intents")
