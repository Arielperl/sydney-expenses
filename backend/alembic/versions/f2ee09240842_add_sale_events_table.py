"""add sale_events table

Revision ID: f2ee09240842
Revises: a4b5c6d7e8f9
Create Date: 2026-09-11 00:00:00.000000

Introduces a persisted, append-only sale event/audit timeline
(`app.models.sale_event.SaleEvent`) — see that module's docstring. This is
purely additive: no existing table, column, or row is touched. Existing
sales simply have no rows in this new table yet; their Sale Details
timeline shows only what's actually known (current status/refund/document
fields) rather than inventing historical events for them.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f2ee09240842'
down_revision: Union[str, None] = 'a4b5c6d7e8f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'sale_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('sale_id', sa.String(length=36), nullable=False),
        sa.Column(
            'event_type',
            sa.Enum(
                'sale_received', 'sale_created_manually', 'sale_imported_from_csv',
                'payment_succeeded', 'payment_pending', 'payment_failed',
                'document_issuance_attempted', 'document_issued', 'document_issuance_failed',
                'refund_partial', 'refund_full', 'sale_details_edited',
                native_enum=False, name='saleeventtype',
            ),
            nullable=False,
        ),
        sa.Column(
            'source',
            sa.Enum('manual', 'webhook', 'csv', 'demo', 'system', native_enum=False, name='saleeventsource'),
            nullable=False,
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['sale_id'], ['sales.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sale_events_sale_id', 'sale_events', ['sale_id'])


def downgrade() -> None:
    op.drop_index('ix_sale_events_sale_id', table_name='sale_events')
    op.drop_table('sale_events')
