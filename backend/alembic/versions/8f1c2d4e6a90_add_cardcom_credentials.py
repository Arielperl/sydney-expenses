"""Add cardcom_credentials — encrypted per-connection Cardcom terminal
credentials, and the webhook_events status/failure_category value set grows
(REJECTED status; IP_NOT_ALLOWED and VERIFICATION_FAILED categories) but
those are plain strings (native_enum=False), so no DDL change is needed for
them — only documented here for completeness.

Kept in its own table, separate from integration_connections, so that table
(shared with Grow and demo-pay) never gains a sensitive, provider-specific
column. See app/models/cardcom_credential.py.
"""

from alembic import op
import sqlalchemy as sa

revision = "8f1c2d4e6a90"
down_revision = "5637fb0df1a1"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "cardcom_credentials",
        sa.Column("connection_id", sa.String(36), sa.ForeignKey("integration_connections.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("terminal_number", sa.String(40), nullable=False),
        sa.Column("encrypted_credentials", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id"), nullable=False),
    )
    op.create_index("ix_cardcom_credentials_business_id", "cardcom_credentials", ["business_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text('ALTER TABLE "cardcom_credentials" ENABLE ROW LEVEL SECURITY'))


def downgrade():
    op.drop_index("ix_cardcom_credentials_business_id", table_name="cardcom_credentials")
    op.drop_table("cardcom_credentials")
