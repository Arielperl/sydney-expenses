"""Add business-owned payment and POS connections."""

from alembic import op
import sqlalchemy as sa

revision = "c842a135d921"
down_revision = "b731b9a0c112"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "integration_connections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("secret_salt", sa.String(64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_event_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id"), nullable=False),
        sa.UniqueConstraint("business_id", "name", name="uq_integration_connections_business_name"),
    )
    op.create_index("ix_integration_connections_business_id", "integration_connections", ["business_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text('ALTER TABLE "integration_connections" ENABLE ROW LEVEL SECURITY'))


def downgrade():
    op.drop_index("ix_integration_connections_business_id", table_name="integration_connections")
    op.drop_table("integration_connections")
