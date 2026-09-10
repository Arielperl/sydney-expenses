"""replace expenses/receipt_uploads with the sales domain model

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-09-10 00:00:00.000000

This is a deliberate product-model change, not a rename: the app now
tracks customer sales/revenue, not business expenses. `expenses` and
`receipt_uploads` are dropped outright rather than reinterpreted in place —
nothing about "money the business spent" is a meaningful "money a customer
paid" once relabeled, so silently repurposing those rows would be
dishonest. All data in every environment this app has run in prior to this
migration is confirmed fictional/demo data (webhook demo transactions and
test uploads), so dropping is safe here; a deployment with real expense
data would need its own separate archival step before running this, which
this migration deliberately does not attempt on its behalf.

`import_batches` is unchanged structurally — it already had no direct
foreign key *from* itself into `expenses` (the reference was the other
way, `expenses.import_batch_id -> import_batches.id`), so nothing here
needs to move.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, None] = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # expenses and receipt_uploads have a circular FK relationship
    # (expenses.suggested_receipt_upload_id -> receipt_uploads.id, and
    # receipt_uploads.expense_id -> expenses.id), resolved at CREATE time via
    # use_alter but not something DROP TABLE unwinds on its own — Postgres
    # enforces the dependency even though SQLite's batch mode did not surface
    # it. Both FK constraints are dropped explicitly first so either table can
    # then be dropped in any order.
    bind = op.get_bind()
    if bind.dialect.name != 'sqlite':
        op.drop_constraint('fk_expenses_suggested_receipt_upload_id', 'expenses', type_='foreignkey')
        op.drop_constraint('receipt_uploads_expense_id_fkey', 'receipt_uploads', type_='foreignkey')
    op.drop_table('expenses')
    op.drop_table('receipt_uploads')

    op.create_table(
        'sales',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('external_id', sa.String(length=255), nullable=True),
        sa.Column('source_provider', sa.String(length=64), nullable=True),
        sa.Column(
            'source',
            sa.Enum('manual', 'csv', 'webhook', native_enum=False, name='salesource'),
            nullable=False,
        ),
        sa.Column(
            'status',
            sa.Enum(
                'succeeded', 'pending', 'failed', 'refunded', 'partially_refunded',
                native_enum=False, name='salestatus',
            ),
            nullable=False,
        ),
        sa.Column('occurred_at', sa.DateTime(), nullable=False),
        sa.Column('customer_name', sa.String(length=255), nullable=False),
        sa.Column('customer_contact', sa.String(length=255), nullable=True),
        sa.Column('service_name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('gross_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('vat_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('processing_fee', sa.Numeric(12, 2), nullable=True),
        sa.Column('net_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('refunded_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('payment_method', sa.String(length=50), nullable=True),
        sa.Column(
            'document_status',
            sa.Enum(
                'pending', 'issued', 'failed', 'not_required',
                native_enum=False, name='documentstatus',
            ),
            nullable=False,
        ),
        sa.Column('document_number', sa.String(length=100), nullable=True),
        sa.Column('document_url', sa.String(length=500), nullable=True),
        sa.Column('raw_description', sa.Text(), nullable=True),
        sa.Column('import_batch_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['import_batch_id'], ['import_batches.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_provider', 'external_id', name='uq_sales_source_provider_external_id'),
    )


def downgrade() -> None:
    op.drop_table('sales')

    op.create_table(
        'expenses',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('business_name', sa.String(length=255), nullable=False),
        sa.Column('receipt_number', sa.String(length=100), nullable=True),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('vat_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column(
            'category',
            sa.Enum(
                'groceries', 'dining', 'transport', 'utilities', 'health', 'shopping',
                'entertainment', 'travel', 'housing', 'other',
                native_enum=False, name='expensecategory',
            ),
            nullable=False,
        ),
        sa.Column('expense_date', sa.Date(), nullable=False),
        sa.Column('payment_method', sa.String(length=50), nullable=True),
        sa.Column('receipt_image_path', sa.String(length=255), nullable=True),
        sa.Column('storage_provider', sa.String(length=32), nullable=True),
        sa.Column('extraction_confidence', sa.Float(), nullable=True),
        sa.Column(
            'extraction_status',
            sa.Enum('manual', 'pending', 'extracted', 'confirmed', 'failed', native_enum=False, name='extractionstatus'),
            nullable=False,
        ),
        sa.Column('notes', sa.String(length=1000), nullable=True),
        sa.Column(
            'source',
            sa.Enum('manual', 'receipt_upload', 'csv', 'webhook', native_enum=False, name='expensesource'),
            nullable=False,
        ),
        sa.Column('external_id', sa.String(length=255), nullable=True),
        sa.Column('source_provider', sa.String(length=64), nullable=True),
        sa.Column('raw_description', sa.Text(), nullable=True),
        sa.Column('occurred_at', sa.DateTime(), nullable=True),
        sa.Column(
            'document_status',
            sa.Enum(
                'missing', 'suggested', 'attached', 'needs_review', 'not_required',
                native_enum=False, name='documentstatus_old',
            ),
            nullable=False,
        ),
        sa.Column('reconciliation_confidence', sa.Float(), nullable=True),
        sa.Column('reconciliation_reasons', sa.JSON(), nullable=True),
        sa.Column('suggested_receipt_upload_id', sa.String(length=36), nullable=True),
        sa.Column('import_batch_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['import_batch_id'], ['import_batches.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_provider', 'external_id', name='uq_expenses_source_provider_external_id'),
    )
    op.create_table(
        'receipt_uploads',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('stored_filename', sa.String(length=255), nullable=False),
        sa.Column('storage_provider', sa.String(length=32), nullable=False),
        sa.Column(
            'status',
            sa.Enum('pending', 'confirmed', 'failed', 'expired', 'discarded', native_enum=False, name='receiptuploadstatus'),
            nullable=False,
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('expense_id', sa.String(length=36), nullable=True),
        sa.Column('extracted_business_name', sa.String(length=255), nullable=True),
        sa.Column('extracted_receipt_number', sa.String(length=100), nullable=True),
        sa.Column('extracted_date', sa.Date(), nullable=True),
        sa.Column('extracted_total', sa.Numeric(12, 2), nullable=True),
        sa.Column('extracted_vat', sa.Numeric(12, 2), nullable=True),
        sa.Column('extracted_currency', sa.String(length=3), nullable=True),
        sa.Column(
            'extracted_category',
            sa.Enum(
                'groceries', 'dining', 'transport', 'utilities', 'health', 'shopping',
                'entertainment', 'travel', 'housing', 'other',
                native_enum=False, name='expensecategory_receiptupload',
            ),
            nullable=True,
        ),
        sa.Column('extraction_confidence', sa.Float(), nullable=True),
        sa.Column('extraction_warnings', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
