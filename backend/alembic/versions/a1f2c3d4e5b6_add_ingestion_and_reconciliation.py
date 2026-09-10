"""add ingestion and reconciliation columns

Revision ID: a1f2c3d4e5b6
Revises: 789ee45c9a55
Create Date: 2026-09-10 00:00:00.000000

Additive-only, non-destructive:
  - creates import_batches
  - adds source/external_id/source_provider/raw_description/occurred_at/
    document_status/reconciliation_confidence/reconciliation_reasons/
    suggested_receipt_upload_id/import_batch_id to expenses
  - adds a UNIQUE(source_provider, external_id) constraint (NULLs never
    collide with each other, so every pre-existing row is unaffected)
  - backfills document_status/source on existing rows: a row that already
    has a receipt_image_path becomes source='receipt_upload',
    document_status='attached'; every other existing row keeps
    source='manual' and becomes document_status='not_required' (a manual
    expense was never expected to have a document, so it must not show up
    as "missing" in the new Reconciliation Inbox).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1f2c3d4e5b6'
down_revision: Union[str, None] = '789ee45c9a55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'import_batches',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('file_hash', sa.String(length=64), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=True),
        sa.Column('status', sa.Enum('pending', 'completed', 'failed', native_enum=False, name='importstatus'), nullable=False),
        sa.Column('valid_row_count', sa.Integer(), nullable=False),
        sa.Column('error_row_count', sa.Integer(), nullable=False),
        sa.Column('created_count', sa.Integer(), nullable=True),
        sa.Column('duplicate_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_import_batches_file_hash'), 'import_batches', ['file_hash'], unique=False)

    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'source',
                sa.Enum('manual', 'receipt_upload', 'csv', 'webhook', native_enum=False, name='expensesource'),
                nullable=False,
                server_default='manual',
            )
        )
        batch_op.add_column(sa.Column('external_id', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('source_provider', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('raw_description', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('occurred_at', sa.DateTime(), nullable=True))
        batch_op.add_column(
            sa.Column(
                'document_status',
                sa.Enum(
                    'missing', 'suggested', 'attached', 'needs_review', 'not_required',
                    native_enum=False, name='documentstatus',
                ),
                nullable=False,
                server_default='not_required',
            )
        )
        batch_op.add_column(sa.Column('reconciliation_confidence', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('reconciliation_reasons', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('suggested_receipt_upload_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('import_batch_id', sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            'fk_expenses_suggested_receipt_upload_id',
            'receipt_uploads',
            ['suggested_receipt_upload_id'],
            ['id'],
            ondelete='SET NULL',
        )
        batch_op.create_foreign_key(
            'fk_expenses_import_batch_id',
            'import_batches',
            ['import_batch_id'],
            ['id'],
            ondelete='SET NULL',
        )
        batch_op.create_unique_constraint(
            'uq_expenses_source_provider_external_id', ['source_provider', 'external_id']
        )

    expenses = sa.table(
        'expenses',
        sa.column('receipt_image_path', sa.String),
        sa.column('source', sa.String),
        sa.column('document_status', sa.String),
    )
    conn = op.get_bind()
    conn.execute(
        expenses.update()
        .where(expenses.c.receipt_image_path.isnot(None))
        .values(source='receipt_upload', document_status='attached')
    )


def downgrade() -> None:
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.drop_constraint('uq_expenses_source_provider_external_id', type_='unique')
        batch_op.drop_constraint('fk_expenses_import_batch_id', type_='foreignkey')
        batch_op.drop_constraint('fk_expenses_suggested_receipt_upload_id', type_='foreignkey')
        batch_op.drop_column('import_batch_id')
        batch_op.drop_column('suggested_receipt_upload_id')
        batch_op.drop_column('reconciliation_reasons')
        batch_op.drop_column('reconciliation_confidence')
        batch_op.drop_column('document_status')
        batch_op.drop_column('occurred_at')
        batch_op.drop_column('raw_description')
        batch_op.drop_column('source_provider')
        batch_op.drop_column('external_id')
        batch_op.drop_column('source')

    op.drop_index(op.f('ix_import_batches_file_hash'), table_name='import_batches')
    op.drop_table('import_batches')
