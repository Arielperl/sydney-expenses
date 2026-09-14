"""Add Grow support: url_token on integration_connections, and a durable
webhook_events inbox table.

url_token is the credential for a URL-token provider (Grow has no signing
capability at all — see app/models/integration_connection.py) — nullable
because demo-pay keeps using its stable `id`-based webhook path.

webhook_events durably records every inbound connection-webhook delivery
before/around Sale creation, specifically because a provider like Grow never
retries a failed delivery — see app/models/webhook_event.py.
"""

from alembic import op
import sqlalchemy as sa

revision = "5637fb0df1a1"
down_revision = "d9137e2a4b10"
branch_labels = depends_on = None


def upgrade():
    with op.batch_alter_table("integration_connections") as batch:
        batch.add_column(sa.Column("url_token", sa.String(64), nullable=True))
        batch.create_unique_constraint("uq_integration_connections_url_token", ["url_token"])

    op.create_table(
        "webhook_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "connection_id", sa.String(36), sa.ForeignKey("integration_connections.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("provider_event_id", sa.String(255), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("sale_id", sa.String(36), sa.ForeignKey("sales.id"), nullable=True),
        sa.Column("failure_category", sa.String(30), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("normalized_customer_name", sa.String(255), nullable=True),
        sa.Column("normalized_customer_contact", sa.String(255), nullable=True),
        sa.Column("normalized_service_name", sa.String(255), nullable=True),
        sa.Column("normalized_description", sa.Text(), nullable=True),
        sa.Column("normalized_gross_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("normalized_vat_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("normalized_tax_treatment", sa.String(20), nullable=True),
        sa.Column("normalized_currency", sa.String(3), nullable=True),
        sa.Column("normalized_occurred_at", sa.DateTime(), nullable=True),
        sa.Column("normalized_external_transaction_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id"), nullable=False),
    )
    op.create_index("ix_webhook_events_business_id", "webhook_events", ["business_id"])
    op.create_index("ix_webhook_events_connection_id", "webhook_events", ["connection_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text('ALTER TABLE "webhook_events" ENABLE ROW LEVEL SECURITY'))


def downgrade():
    op.drop_index("ix_webhook_events_connection_id", table_name="webhook_events")
    op.drop_index("ix_webhook_events_business_id", table_name="webhook_events")
    op.drop_table("webhook_events")
    with op.batch_alter_table("integration_connections") as batch:
        batch.drop_constraint("uq_integration_connections_url_token", type_="unique")
        batch.drop_column("url_token")
