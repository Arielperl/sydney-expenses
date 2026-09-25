"""Add threaded messages to support requests.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
"""

from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "support_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_id", sa.String(36), sa.ForeignKey("support_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_user_id", sa.String(128), nullable=False),
        sa.Column("author_type", sa.String(16), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("author_type in ('customer','staff')", name="ck_support_message_author_type"),
    )
    op.create_index("ix_support_messages_business_id", "support_messages", ["business_id"])
    op.create_index("ix_support_messages_request_id", "support_messages", ["request_id"])
    op.create_index("ix_support_messages_request_created", "support_messages", ["request_id", "created_at"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text('ALTER TABLE "support_messages" ENABLE ROW LEVEL SECURITY'))


def downgrade() -> None:
    op.drop_index("ix_support_messages_request_created", table_name="support_messages")
    op.drop_index("ix_support_messages_request_id", table_name="support_messages")
    op.drop_index("ix_support_messages_business_id", table_name="support_messages")
    op.drop_table("support_messages")
