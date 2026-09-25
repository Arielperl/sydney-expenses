"""Add the superadmin platform role.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
"""
from alembic import op


revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("app_accounts") as batch:
        batch.drop_constraint("ck_app_account_system_role", type_="check")
        batch.create_check_constraint(
            "ck_app_account_system_role",
            "system_role in ('user','support','admin','superadmin')",
        )
    op.execute(
        "UPDATE app_accounts SET system_role = 'superadmin' "
        "WHERE lower(email) = 'arielperl999@gmail.com'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE app_accounts SET system_role = 'admin' "
        "WHERE system_role = 'superadmin'"
    )
    with op.batch_alter_table("app_accounts") as batch:
        batch.drop_constraint("ck_app_account_system_role", type_="check")
        batch.create_check_constraint(
            "ck_app_account_system_role",
            "system_role in ('user','support','admin')",
        )
