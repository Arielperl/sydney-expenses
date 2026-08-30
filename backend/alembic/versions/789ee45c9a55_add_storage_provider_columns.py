"""add storage_provider columns

Revision ID: 789ee45c9a55
Revises: ebd92ecf7c41
Create Date: 2026-08-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '789ee45c9a55'
down_revision: Union[str, None] = 'ebd92ecf7c41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Additive-only, non-destructive. server_default backfills every existing row
    # (which was always stored on local disk before this column existed) as
    # 'local', so a pre-existing receipt keeps resolving through LocalReceiptStorage
    # regardless of what STORAGE_PROVIDER is configured to today.
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('storage_provider', sa.String(length=32), nullable=True, server_default='local'))

    with op.batch_alter_table('receipt_uploads', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('storage_provider', sa.String(length=32), nullable=False, server_default='local')
        )


def downgrade() -> None:
    with op.batch_alter_table('receipt_uploads', schema=None) as batch_op:
        batch_op.drop_column('storage_provider')

    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.drop_column('storage_provider')
