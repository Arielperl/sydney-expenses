"""Add DB-backed platform roles and per-business payment providers.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
"""

from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None

ADMIN_EMAIL = "arielperl999@gmail.com"


def upgrade() -> None:
    op.create_table(
        "app_accounts",
        sa.Column("user_id", sa.String(128), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("display_name", sa.String(100), nullable=False, server_default=""),
        sa.Column("system_role", sa.String(16), nullable=False, server_default="user"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("system_role in ('user','admin')", name="ck_app_account_system_role"),
    )
    op.create_table(
        "business_payment_providers",
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("provider", sa.String(40), primary_key=True),
        sa.Column("added_by_user_id", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("provider in ('grow','cardcom')", name="ck_business_payment_provider"),
        sa.UniqueConstraint("business_id", "provider", name="uq_business_payment_provider"),
    )
    op.create_index("ix_business_payment_providers_business_id", "business_payment_providers", ["business_id"])

    # Existing businesses already had both production panels visible. Preserve
    # that behavior until their admin narrows the selection explicitly.
    op.execute(
        sa.text(
            """
            INSERT INTO business_payment_providers (business_id, provider, added_by_user_id)
            SELECT id, 'grow', 'migration' FROM businesses
            UNION ALL
            SELECT id, 'cardcom', 'migration' FROM businesses
            """
        )
    )

    # Supabase keeps verified identities in auth.users. Seed the requested
    # administrator directly into our DB-backed role table when that schema
    # exists; generic PostgreSQL/SQLite environments simply skip this block.
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        op.execute(sa.text('ALTER TABLE "app_accounts" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text('ALTER TABLE "business_payment_providers" ENABLE ROW LEVEL SECURITY'))
        has_auth_users = connection.execute(sa.text("SELECT to_regclass('auth.users')")).scalar()
        if has_auth_users:
            connection.execute(
                sa.text(
                    """
                    INSERT INTO app_accounts (user_id, email, display_name, system_role)
                    SELECT id::text, lower(email), coalesce(raw_user_meta_data->>'full_name', ''), 'admin'
                    FROM auth.users
                    WHERE lower(email) = :email
                    ON CONFLICT (user_id) DO UPDATE
                    SET email = EXCLUDED.email, display_name = EXCLUDED.display_name,
                        system_role = 'admin', updated_at = now()
                    """
                ),
                {"email": ADMIN_EMAIL},
            )


def downgrade() -> None:
    op.drop_index("ix_business_payment_providers_business_id", table_name="business_payment_providers")
    op.drop_table("business_payment_providers")
    op.drop_table("app_accounts")
