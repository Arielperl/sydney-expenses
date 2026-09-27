"""Make the support feature claim precise.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: str | None = "b8c9d0e1f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _plans():
    return sa.table(
        "subscription_plans",
        sa.column("code", sa.String()),
        sa.column("features", sa.JSON()),
    )


def upgrade() -> None:
    plans = _plans()
    op.execute(
        sa.update(plans).where(plans.c.code == "starter").values(features=[
            "תמונה ברורה של ההכנסות, המע״מ והעמלות",
            "ריכוז המכירות ופרטי הלקוחות במקום אחד",
            "אפשרות להוסיף מכירות גם ממערכות אחרות",
            "התראות כשעסקה דורשת בדיקה",
            "שליחת פניות ומעקב אחריהן מתוך המערכת",
        ])
    )


def downgrade() -> None:
    plans = _plans()
    op.execute(
        sa.update(plans).where(plans.c.code == "starter").values(features=[
            "תמונה ברורה של ההכנסות, המע״מ והעמלות",
            "כל המכירות והלקוחות במקום אחד",
            "אפשרות להוסיף מכירות גם ממערכות אחרות",
            "התראות כשעסקה דורשת בדיקה",
            "תמיכה אנושית בכל שלב",
        ])
    )
