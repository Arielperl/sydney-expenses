"""Add Sydney subscription billing (plans, trials, subscriptions, usage).

Revision ID: d7e8f9a0b1c2
Revises: e5f6a7b8c9d0

Additive: eight new tables; no existing table or row is altered or deleted.

Existing businesses (data step)
-------------------------------
Every real business — one with at least one member, excluding the legacy
placeholder business — that has no subscription yet receives a fresh 30-day
trial starting when this migration runs:

* plan ``business`` (the recommended plan), or ``pro`` when the business
  already has more than three sales connections, so no existing connection
  is ever over its plan's limit;
* the owner's email and the business number (when present) are recorded as
  having used their trial, exactly like a trial started in the app;
* an audit event ``trial_granted_on_migration`` (source ``system``).

Nobody is locked out by this migration: lockout additionally requires
``BILLING_ENFORCEMENT_ENABLED``, which production refuses without a working
billing provider.

The downgrade drops the billing tables. It is only safe before any business
has paid; afterwards the subscription history must be retained.
"""

import hashlib
import re
import uuid
from datetime import datetime, timedelta

import sqlalchemy as sa
from alembic import op

revision = "d7e8f9a0b1c2"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None

LEGACY_BUSINESS_ID = "00000000-0000-4000-8000-000000000001"
TRIAL_DAYS = 30
STATUSES = ("trialing", "active", "past_due", "canceled", "expired")

# A frozen copy of app/billing/plans.py at the time of this migration
# (tests/test_billing_migration.py checks they agree).
PLANS = [
    # code, name, tagline, sort, recommended, connections, members, ai/month, priority, features, monthly, yearly
    ("starter", "Starter", "לעסק שמתחיל לעבוד עם מקור מכירות אחד", 1, False, 1, 1, 300, False,
     ["לוח בקרה ותמונת הכנסות מלאה", "רשימת מכירות וחיפוש", "ייבוא מכירות מקובץ CSV", "מרכז ״דורש טיפול״", "פניות לתמיכה"],
     6_900, 69_000),
    ("business", "Business", "המסלול המומלץ לרוב העסקים", 2, True, 3, 5, 1_500, True,
     ["כל מה שיש ב־Starter", "סימון עדיפות בפניות לתמיכה"], 11_900, 119_000),
    ("pro", "Pro", "לעסק שמוכר דרך כמה מקורות מכירה", 3, False, 10, 15, 5_000, True,
     ["כל מה שיש ב־Business", "מתאים לעסקים עם כמה מקורות מכירה"], 24_900, 249_000),
]


def _in(column, values):
    return f"{column} in ({', '.join(repr(v) for v in values)})"


def _identity_hash(kind: str, value: str) -> str:
    normalized = re.sub(r"\s+", "", value).lower() if kind == "email" else re.sub(r"\D", "", value)
    return hashlib.sha256(f"sydney-trial:{kind}:{normalized}".encode()).hexdigest()


def upgrade() -> None:
    plans = op.create_table(
        "subscription_plans",
        sa.Column("code", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("tagline", sa.String(160), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("recommended", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("max_connections", sa.Integer(), nullable=False),
        sa.Column("max_members", sa.Integer(), nullable=False),
        sa.Column("ai_questions_per_month", sa.Integer(), nullable=False),
        sa.Column("priority_support", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("max_connections >= 0", name="ck_subscription_plans_connections"),
        sa.CheckConstraint("max_members >= 1", name="ck_subscription_plans_members"),
        sa.CheckConstraint("ai_questions_per_month >= 0", name="ck_subscription_plans_ai"),
    )
    prices = op.create_table(
        "subscription_plan_prices",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("plan_code", sa.String(32), sa.ForeignKey("subscription_plans.code"), nullable=False),
        sa.Column("interval", sa.String(8), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="ILS"),
        sa.Column("provider_price_ref", sa.String(255), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("plan_code", "interval", "currency", name="uq_subscription_plan_prices_plan_interval"),
        sa.CheckConstraint("interval in ('month', 'year')", name="ck_subscription_plan_prices_interval"),
        sa.CheckConstraint("amount_minor > 0", name="ck_subscription_plan_prices_amount"),
        sa.CheckConstraint("currency = 'ILS'", name="ck_subscription_plan_prices_currency"),
    )
    op.create_table(
        "business_subscriptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("plan_code", sa.String(32), sa.ForeignKey("subscription_plans.code"), nullable=False),
        sa.Column("billing_interval", sa.String(8), nullable=False, server_default="month"),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("trial_started_at", sa.DateTime(), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(), nullable=True),
        sa.Column("current_period_start", sa.DateTime(), nullable=True),
        sa.Column("current_period_end", sa.DateTime(), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("canceled_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("pending_plan_code", sa.String(32), sa.ForeignKey("subscription_plans.code"), nullable=True),
        sa.Column("payment_method_on_file", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("provider", sa.String(40), nullable=True),
        sa.Column("provider_customer_ref", sa.String(255), nullable=True),
        sa.Column("provider_subscription_ref", sa.String(255), nullable=True),
        sa.Column("created_by_user_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("business_id", name="uq_business_subscriptions_business"),
        sa.UniqueConstraint("provider", "provider_subscription_ref", name="uq_business_subscriptions_provider_ref"),
        sa.CheckConstraint(_in("status", STATUSES), name="ck_business_subscriptions_status"),
        sa.CheckConstraint("billing_interval in ('month', 'year')", name="ck_business_subscriptions_interval"),
        sa.CheckConstraint(
            "(trial_started_at IS NULL AND trial_ends_at IS NULL) OR "
            "(trial_started_at IS NOT NULL AND trial_ends_at IS NOT NULL AND trial_ends_at > trial_started_at)",
            name="ck_business_subscriptions_trial_window",
        ),
        sa.CheckConstraint("status <> 'trialing' OR trial_ends_at IS NOT NULL", name="ck_business_subscriptions_trialing_has_end"),
        sa.CheckConstraint(
            "current_period_start IS NULL OR current_period_end IS NULL OR current_period_end > current_period_start",
            name="ck_business_subscriptions_period_window",
        ),
        sa.CheckConstraint("version >= 1", name="ck_business_subscriptions_version"),
    )
    op.create_index("ix_business_subscriptions_business_id", "business_subscriptions", ["business_id"])
    op.create_index("ix_business_subscriptions_status_trial_end", "business_subscriptions", ["status", "trial_ends_at"])

    op.create_table(
        "subscription_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("subscription_id", sa.String(36), sa.ForeignKey("business_subscriptions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(48), nullable=False),
        sa.Column("from_status", sa.String(16), nullable=True),
        sa.Column("to_status", sa.String(16), nullable=True),
        sa.Column("from_plan", sa.String(32), nullable=True),
        sa.Column("to_plan", sa.String(32), nullable=True),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("actor_user_id", sa.String(128), nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("subscription_id", "sequence", name="uq_subscription_events_sequence"),
        sa.CheckConstraint("source in ('owner', 'provider', 'system', 'admin')", name="ck_subscription_events_source"),
        sa.CheckConstraint("sequence >= 1", name="ck_subscription_events_sequence"),
        sa.CheckConstraint("source <> 'admin' OR (actor_user_id IS NOT NULL AND reason IS NOT NULL)",
                           name="ck_subscription_events_admin_reason"),
    )
    op.create_index("ix_subscription_events_business_id", "subscription_events", ["business_id"])
    op.create_index("ix_subscription_events_subscription_created", "subscription_events", ["subscription_id", "created_at"])

    op.create_table(
        "billing_checkout_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("subscription_id", sa.String(36), sa.ForeignKey("business_subscriptions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("provider_session_ref", sa.String(255), nullable=True),
        sa.Column("plan_code", sa.String(32), sa.ForeignKey("subscription_plans.code"), nullable=False),
        sa.Column("interval", sa.String(8), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("checkout_url", sa.String(2048), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("created_by_user_id", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("business_id", "idempotency_key", name="uq_billing_checkout_sessions_idempotency"),
        sa.UniqueConstraint("provider", "provider_session_ref", name="uq_billing_checkout_sessions_provider_ref"),
        sa.CheckConstraint("status in ('open', 'completed', 'expired', 'canceled')", name="ck_billing_checkout_sessions_status"),
        sa.CheckConstraint("interval in ('month', 'year')", name="ck_billing_checkout_sessions_interval"),
        sa.CheckConstraint("checkout_url IS NULL OR checkout_url LIKE 'https://%'", name="ck_billing_checkout_sessions_https"),
    )
    op.create_index("ix_billing_checkout_sessions_business_id", "billing_checkout_sessions", ["business_id"])

    op.create_table(
        "billing_webhook_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("provider_event_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id"), nullable=True),
        sa.Column("subscription_id", sa.String(36), sa.ForeignKey("business_subscriptions.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("payload_summary", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="received"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("provider", "provider_event_id", name="uq_billing_webhook_events_provider_event"),
        sa.CheckConstraint("status in ('received', 'processed', 'ignored', 'failed')", name="ck_billing_webhook_events_status"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_billing_webhook_events_attempts"),
    )
    op.create_index("ix_billing_webhook_events_business_id", "billing_webhook_events", ["business_id"])
    op.create_index("ix_billing_webhook_events_status", "billing_webhook_events", ["status", "received_at"])

    op.create_table(
        "billing_usage_counters",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("metric", sa.String(32), nullable=False),
        sa.Column("period_start", sa.DateTime(), nullable=False),
        sa.Column("period_end", sa.DateTime(), nullable=False),
        sa.Column("used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("business_id", "metric", "period_start", name="uq_billing_usage_counters_period"),
        sa.CheckConstraint("metric in ('ai_questions')", name="ck_billing_usage_counters_metric"),
        sa.CheckConstraint("used >= 0", name="ck_billing_usage_counters_used"),
        sa.CheckConstraint("period_end > period_start", name="ck_billing_usage_counters_window"),
    )
    op.create_index("ix_billing_usage_counters_business_id", "billing_usage_counters", ["business_id"])

    op.create_table(
        "billing_trial_claims",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("identity_hash", sa.String(64), nullable=False),
        sa.Column("identity_kind", sa.String(24), nullable=False),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("identity_hash", name="uq_billing_trial_claims_identity"),
    )
    op.create_index("ix_billing_trial_claims_business_id", "billing_trial_claims", ["business_id"])

    # ---- seed the plan catalog ----
    op.bulk_insert(plans, [
        {"code": code, "name": name, "tagline": tagline, "sort_order": sort, "recommended": recommended, "active": True,
         "max_connections": connections, "max_members": members, "ai_questions_per_month": ai, "priority_support": priority,
         "features": features}
        for code, name, tagline, sort, recommended, connections, members, ai, priority, features, _, _ in PLANS
    ])
    op.bulk_insert(prices, [
        {"id": str(uuid.uuid4()), "plan_code": code, "interval": interval, "amount_minor": amount, "currency": "ILS", "active": True}
        for code, *_rest, monthly, yearly in PLANS
        for interval, amount in (("month", monthly), ("year", yearly))
    ])

    # ---- existing businesses: a fresh 30-day trial from deployment ----
    bind = op.get_bind()
    now = datetime.utcnow().replace(microsecond=0)
    ends = now + timedelta(days=TRIAL_DAYS)
    businesses = bind.execute(sa.text(
        "SELECT b.id, b.business_number, "
        "  (SELECT COUNT(*) FROM integration_connections c WHERE c.business_id = b.id) AS connections "
        "FROM businesses b "
        "WHERE b.id <> :legacy "
        "  AND EXISTS (SELECT 1 FROM business_members m WHERE m.business_id = b.id)"
    ), {"legacy": LEGACY_BUSINESS_ID}).fetchall()
    for business_id, business_number, connections in businesses:
        plan = "pro" if connections > 3 else "business"
        subscription_id = str(uuid.uuid4())
        bind.execute(sa.text(
            "INSERT INTO business_subscriptions (id, business_id, plan_code, billing_interval, status, trial_started_at, "
            "trial_ends_at, cancel_at_period_end, payment_method_on_file, created_at, updated_at, version) "
            "VALUES (:id, :business, :plan, 'month', 'trialing', :start, :end, :false, :false, :start, :start, 1)"
        ), {"id": subscription_id, "business": business_id, "plan": plan, "start": now, "end": ends, "false": False})
        bind.execute(sa.text(
            "INSERT INTO subscription_events (id, business_id, subscription_id, sequence, event_type, to_status, to_plan, "
            "source, details, created_at) VALUES (:id, :business, :sub, 1, 'trial_granted_on_migration', 'trialing', :plan, "
            "'system', :details, :now)"
        ), {"id": str(uuid.uuid4()), "business": business_id, "sub": subscription_id, "plan": plan,
            "details": '{"reason": "existing business at billing launch"}', "now": now})
        emails = bind.execute(sa.text(
            "SELECT a.email FROM business_members m JOIN app_accounts a ON a.user_id = m.user_id "
            "WHERE m.business_id = :business AND m.role = 'owner'"
        ), {"business": business_id}).scalars().all()
        identities = [("email", _identity_hash("email", email)) for email in emails if email]
        if business_number and re.sub(r"\D", "", business_number):
            identities.append(("business_number", _identity_hash("business_number", business_number)))
        for kind, value in identities:
            exists = bind.execute(sa.text("SELECT 1 FROM billing_trial_claims WHERE identity_hash = :h"), {"h": value}).first()
            if not exists:
                bind.execute(sa.text(
                    "INSERT INTO billing_trial_claims (id, identity_hash, identity_kind, business_id, created_at) "
                    "VALUES (:id, :h, :kind, :business, :now)"
                ), {"id": str(uuid.uuid4()), "h": value, "kind": kind, "business": business_id, "now": now})

    tables = ("subscription_plans", "subscription_plan_prices", "business_subscriptions", "subscription_events",
              "billing_checkout_sessions", "billing_webhook_events", "billing_usage_counters", "billing_trial_claims")
    dialect = bind.dialect.name
    if dialect == "postgresql":
        op.execute(sa.text(
            "CREATE FUNCTION subscription_events_immutable() RETURNS trigger AS $$ "
            "BEGIN RAISE EXCEPTION 'subscription_events is append-only'; END; $$ LANGUAGE plpgsql"
        ))
        op.execute(sa.text(
            "CREATE TRIGGER trg_subscription_events_immutable BEFORE UPDATE OR DELETE ON subscription_events "
            "FOR EACH ROW EXECUTE FUNCTION subscription_events_immutable()"
        ))
        for table in tables:
            op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
    elif dialect == "sqlite":
        for action in ("UPDATE", "DELETE"):
            op.execute(sa.text(
                f"CREATE TRIGGER trg_subscription_events_no_{action.lower()} BEFORE {action} ON subscription_events "
                "BEGIN SELECT RAISE(ABORT, 'subscription_events is append-only'); END"
            ))


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(sa.text("DROP TRIGGER IF EXISTS trg_subscription_events_immutable ON subscription_events"))
        op.execute(sa.text("DROP FUNCTION IF EXISTS subscription_events_immutable()"))
    elif dialect == "sqlite":
        for action in ("update", "delete"):
            op.execute(sa.text(f"DROP TRIGGER IF EXISTS trg_subscription_events_no_{action}"))
    for index, table in (
        ("ix_billing_trial_claims_business_id", "billing_trial_claims"),
        ("ix_billing_usage_counters_business_id", "billing_usage_counters"),
        ("ix_billing_webhook_events_status", "billing_webhook_events"),
        ("ix_billing_webhook_events_business_id", "billing_webhook_events"),
        ("ix_billing_checkout_sessions_business_id", "billing_checkout_sessions"),
        ("ix_subscription_events_subscription_created", "subscription_events"),
        ("ix_subscription_events_business_id", "subscription_events"),
        ("ix_business_subscriptions_status_trial_end", "business_subscriptions"),
        ("ix_business_subscriptions_business_id", "business_subscriptions"),
    ):
        op.drop_index(index, table_name=table)
    for table in ("billing_trial_claims", "billing_usage_counters", "billing_webhook_events", "billing_checkout_sessions",
                  "subscription_events", "business_subscriptions", "subscription_plan_prices", "subscription_plans"):
        op.drop_table(table)
