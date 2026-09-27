"""Refine the Starter plan's customer-facing value copy.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d0e1f2a3b4c5"
down_revision: str | None = "c9d0e1f2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _plans():
    return sa.table(
        "subscription_plans",
        sa.column("code", sa.String()),
        sa.column("tagline", sa.String()),
        sa.column("features", sa.JSON()),
    )


def upgrade() -> None:
    plans = _plans()
    op.execute(
        sa.update(plans).where(plans.c.code == "starter").values(
            tagline="לעסק קטן שרוצה לראות ולנהל את ההכנסות במקום אחד",
            features=[
                "לוח בקרה של הכנסות, מע״מ, עמלות וזיכויים",
                "פירוט המכירות ופרטי הלקוחות במקום אחד",
                "זיהוי עסקאות שנכשלו או שחסר בהן מידע",
                "עוזר עסקי שעונה על שאלות לפי נתוני המכירות",
            ],
        )
    )


def downgrade() -> None:
    plans = _plans()
    op.execute(
        sa.update(plans).where(plans.c.code == "starter").values(
            tagline="לעסק שרוצה סדר ושליטה בהכנסות",
            features=[
                "תמונה ברורה של ההכנסות, המע״מ והעמלות",
                "ריכוז המכירות ופרטי הלקוחות במקום אחד",
                "אפשרות להוסיף מכירות גם ממערכות אחרות",
                "התראות כשעסקה דורשת בדיקה",
                "שליחת פניות ומעקב אחריהן מתוך המערכת",
            ],
        )
    )
