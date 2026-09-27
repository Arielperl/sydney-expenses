"""Remove subscription-based support priority from the plan catalog.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    plans = sa.table(
        "subscription_plans",
        sa.column("code", sa.String()),
        sa.column("priority_support", sa.Boolean()),
        sa.column("features", sa.JSON()),
    )
    op.execute(sa.update(plans).values(priority_support=False))
    op.execute(
        sa.update(plans)
        .where(plans.c.code == "business")
        .values(features=["כל מה שיש ב־Starter", "תמונה מאוחדת מכמה מקורות מכירה"])
    )


def downgrade() -> None:
    plans = sa.table(
        "subscription_plans",
        sa.column("code", sa.String()),
        sa.column("priority_support", sa.Boolean()),
        sa.column("features", sa.JSON()),
    )
    op.execute(
        sa.update(plans)
        .where(plans.c.code == "business")
        .values(priority_support=True, features=["כל מה שיש ב־Starter", "סימון עדיפות בפניות לתמיכה"])
    )
    op.execute(sa.update(plans).where(plans.c.code == "pro").values(priority_support=True))
