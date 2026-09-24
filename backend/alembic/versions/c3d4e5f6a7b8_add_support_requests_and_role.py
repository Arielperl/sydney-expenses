"""Add support role and tenant-owned requests.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
"""
from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_accounts", sa.Column("disabled_at", sa.DateTime(), nullable=True))
    with op.batch_alter_table("app_accounts") as batch:
        batch.drop_constraint("ck_app_account_system_role", type_="check")
        batch.create_check_constraint("ck_app_account_system_role", "system_role in ('user','admin','support')")
    op.create_table(
        "support_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requester_user_id", sa.String(128), nullable=False),
        sa.Column("subject", sa.String(160), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(80), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status in ('open','resolved')", name="ck_support_request_status"),
    )
    op.create_index("ix_support_requests_business_id", "support_requests", ["business_id"])
    op.create_index("ix_support_requests_status_created", "support_requests", ["status", "created_at"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text('ALTER TABLE "support_requests" ENABLE ROW LEVEL SECURITY'))


def downgrade() -> None:
    op.drop_index("ix_support_requests_status_created", table_name="support_requests")
    op.drop_index("ix_support_requests_business_id", table_name="support_requests")
    op.drop_table("support_requests")
    op.drop_column("app_accounts", "disabled_at")
    with op.batch_alter_table("app_accounts") as batch:
        batch.drop_constraint("ck_app_account_system_role", type_="check")
        batch.create_check_constraint("ck_app_account_system_role", "system_role in ('user','admin')")
