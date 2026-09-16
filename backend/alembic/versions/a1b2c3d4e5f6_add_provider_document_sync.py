"""Add provider-document sync — automatic linking of a customer document
Grow or Cardcom already generated, so an owner doesn't need to manually
upload a receipt/invoice for every sale.

- `sales.document_type`: the provider's own document type label (e.g.
  Cardcom's "TaxInvoiceAndReceipt"). Nullable — Grow's invoice webhook
  never sends a type, so it's always null for Grow.
- `sales.document_url` widened from 500 to 2000 characters — a provider
  invoice URL can legitimately be longer than a locally-stored image path.
- `provider_document_events`: a durable, business/connection-scoped queue
  for a provider document event that arrived before its matching Sale
  (Grow's invoice webhook may arrive before or after the payment webhook —
  see app/models/provider_document_event.py).

`DocumentStatus.WAITING_AUTOMATIC` (the new value distinguishing "an
automatic provider document is expected but hasn't arrived yet" from the
existing generic `pending`) and `ProviderDocumentStatus` are both stored as
plain strings (`native_enum=False`, matching every other enum column in
this codebase), so neither needs any DDL of its own — only documented here
for completeness, the same pattern used by 8f1c2d4e6a90.
"""

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "8f1c2d4e6a90"
branch_labels = depends_on = None


def upgrade():
    with op.batch_alter_table("sales") as batch:
        batch.add_column(sa.Column("document_type", sa.String(100), nullable=True))
        batch.alter_column("document_url", type_=sa.String(2000), existing_type=sa.String(500))

    op.create_table(
        "provider_document_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "connection_id", sa.String(36), sa.ForeignKey("integration_connections.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("external_transaction_id", sa.String(255), nullable=False),
        sa.Column("document_number", sa.String(100), nullable=True),
        sa.Column("document_type", sa.String(100), nullable=True),
        sa.Column("document_url", sa.String(2000), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("matched_sale_id", sa.String(36), sa.ForeignKey("sales.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id"), nullable=False),
        sa.UniqueConstraint(
            "connection_id", "external_transaction_id", name="uq_provider_document_events_connection_txn"
        ),
    )
    op.create_index("ix_provider_document_events_connection_id", "provider_document_events", ["connection_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text('ALTER TABLE "provider_document_events" ENABLE ROW LEVEL SECURITY'))


def downgrade():
    op.drop_index("ix_provider_document_events_connection_id", table_name="provider_document_events")
    op.drop_table("provider_document_events")
    with op.batch_alter_table("sales") as batch:
        batch.alter_column("document_url", type_=sa.String(500), existing_type=sa.String(2000))
        batch.drop_column("document_type")
