"""add persisted extraction snapshot to receipt_uploads

Revision ID: c2d3e4f5a6b7
Revises: a1f2c3d4e5b6
Create Date: 2026-09-10 00:00:00.000000

Additive-only, non-destructive: adds 9 nullable snapshot columns to
receipt_uploads. Pre-existing rows get NULL — the extraction result for
those uploads was genuinely never persisted under the old code, so NULL is
the honest value, not a gap to backfill. `discarded` also becomes a valid
value for the existing status column, but since it's stored as a plain
VARCHAR (native_enum=False, no CHECK constraint), that needs no DDL change
here — it's already just a Python-level addition to ReceiptUploadStatus.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, None] = 'a1f2c3d4e5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('receipt_uploads', schema=None) as batch_op:
        batch_op.add_column(sa.Column('extracted_business_name', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('extracted_receipt_number', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('extracted_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('extracted_total', sa.Numeric(12, 2), nullable=True))
        batch_op.add_column(sa.Column('extracted_vat', sa.Numeric(12, 2), nullable=True))
        batch_op.add_column(sa.Column('extracted_currency', sa.String(length=3), nullable=True))
        batch_op.add_column(
            sa.Column(
                'extracted_category',
                sa.Enum(
                    'groceries', 'dining', 'transport', 'utilities', 'health', 'shopping',
                    'entertainment', 'travel', 'housing', 'other',
                    native_enum=False, name='expensecategory',
                ),
                nullable=True,
            )
        )
        batch_op.add_column(sa.Column('extraction_confidence', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('extraction_warnings', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('receipt_uploads', schema=None) as batch_op:
        batch_op.drop_column('extraction_warnings')
        batch_op.drop_column('extraction_confidence')
        batch_op.drop_column('extracted_category')
        batch_op.drop_column('extracted_currency')
        batch_op.drop_column('extracted_vat')
        batch_op.drop_column('extracted_total')
        batch_op.drop_column('extracted_date')
        batch_op.drop_column('extracted_receipt_number')
        batch_op.drop_column('extracted_business_name')
