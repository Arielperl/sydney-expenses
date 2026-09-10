"""add tax_treatment, tax_treatment_needs_review, and vat_rate to sales

Revision ID: a4b5c6d7e8f9
Revises: d3e4f5a6b7c8
Create Date: 2026-09-10 00:00:00.000000

Introduces Israeli VAT tax-treatment tracking on `sales` (see
app.domain.demo_business and app.services.tax.vat): `tax_treatment`
(standard/zero_rate/exempt), `tax_treatment_needs_review` (flags a legacy
row this migration could not safely classify), and `vat_rate` (a snapshot
of the rate actually used, so a future change to the business's configured
standard rate can never rewrite a historical sale's VAT).

Existing rows are never silently rewritten. For each sale already in the
table, this migration inspects its existing `vat_amount` against
`gross_amount`:
  - If `vat_amount` is present, positive, and matches what the Israeli
    standard-VAT formula (`gross * 18/118`, rounded) would have produced
    within a one-cent tolerance, the row is classified `standard` and
    stamped with the current standard rate as its snapshot — this is a
    read-only classification of data that's already there, not an invented
    value.
  - Every other case — `vat_amount` is null (never recorded), exactly zero
    (ambiguous between `zero_rate` and `exempt`, which this migration
    cannot tell apart), or present but not matching the standard formula —
    is left with `tax_treatment` NULL and `tax_treatment_needs_review=True`
    rather than guessing. No `gross_amount`, `vat_amount`, `net_amount`, or
    any other financial figure is ever modified by this migration.
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a4b5c6d7e8f9'
down_revision: Union[str, None] = 'd3e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STANDARD_VAT_RATE = Decimal("0.18")
VAT_TOLERANCE = Decimal("0.01")


def _expected_standard_vat(gross_amount: Decimal) -> Decimal:
    vat = gross_amount * STANDARD_VAT_RATE / (Decimal("1") + STANDARD_VAT_RATE)
    return vat.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def upgrade() -> None:
    op.add_column(
        'sales',
        sa.Column(
            'tax_treatment',
            sa.Enum('standard', 'zero_rate', 'exempt', native_enum=False, name='taxtreatment'),
            nullable=True,
        ),
    )
    op.add_column(
        'sales',
        sa.Column('tax_treatment_needs_review', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column('sales', sa.Column('vat_rate', sa.Numeric(6, 4), nullable=True))

    bind = op.get_bind()
    sales_table = sa.table(
        'sales',
        sa.column('id', sa.String),
        sa.column('gross_amount', sa.Numeric),
        sa.column('vat_amount', sa.Numeric),
    )
    rows = bind.execute(sa.select(sales_table.c.id, sales_table.c.gross_amount, sales_table.c.vat_amount)).fetchall()
    for sale_id, gross_amount, vat_amount in rows:
        classified_standard = False
        if gross_amount is not None and vat_amount is not None:
            gross_amount_dec = Decimal(str(gross_amount))
            vat_amount_dec = Decimal(str(vat_amount))
            if gross_amount_dec > 0 and vat_amount_dec > 0:
                expected = _expected_standard_vat(gross_amount_dec)
                if abs(vat_amount_dec - expected) <= VAT_TOLERANCE:
                    classified_standard = True

        if classified_standard:
            bind.execute(
                sa.text(
                    "UPDATE sales SET tax_treatment = :treatment, vat_rate = :rate, "
                    "tax_treatment_needs_review = false WHERE id = :id"
                ),
                {"treatment": "standard", "rate": str(STANDARD_VAT_RATE), "id": sale_id},
            )
        else:
            # Ambiguous: vat_amount is null, exactly zero (could be
            # zero_rate OR exempt — indistinguishable from the number
            # alone), or doesn't match the standard formula. Never invent a
            # value here; flag for a human to review instead.
            bind.execute(
                sa.text("UPDATE sales SET tax_treatment_needs_review = true WHERE id = :id"),
                {"id": sale_id},
            )

    # The server default only exists to backfill this NOT NULL column on
    # rows that predate it, in the statement above — every row going
    # forward sets it explicitly at the application layer (see
    # app/api/routes/sales.py, app/services/ingestion/), so the server-side
    # default is removed once the backfill is done.
    op.alter_column('sales', 'tax_treatment_needs_review', server_default=None)


def downgrade() -> None:
    op.drop_column('sales', 'vat_rate')
    op.drop_column('sales', 'tax_treatment_needs_review')
    op.drop_column('sales', 'tax_treatment')
