"""Rewrite customer-facing plan copy and recommend Starter.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _plans():
    return sa.table(
        "subscription_plans",
        sa.column("code", sa.String()),
        sa.column("tagline", sa.String()),
        sa.column("recommended", sa.Boolean()),
        sa.column("features", sa.JSON()),
    )


def upgrade() -> None:
    plans = _plans()
    op.execute(
        sa.update(plans).where(plans.c.code == "starter").values(
            tagline="לעסק שרוצה סדר ושליטה בהכנסות",
            recommended=True,
            features=[
                "תמונה ברורה של ההכנסות, המע״מ והעמלות",
                "כל המכירות והלקוחות במקום אחד",
                "אפשרות להוסיף מכירות גם ממערכות אחרות",
                "התראות כשעסקה דורשת בדיקה",
                "תמיכה אנושית בכל שלב",
            ],
        )
    )
    op.execute(
        sa.update(plans).where(plans.c.code == "business").values(
            tagline="לעסק שמקבל תשלומים מכמה מקומות",
            recommended=False,
        )
    )
    op.execute(
        sa.update(plans).where(plans.c.code == "pro").values(
            tagline="לעסק עם פעילות רחבה ומספר מערכות מכירה",
            recommended=False,
        )
    )


def downgrade() -> None:
    plans = _plans()
    op.execute(
        sa.update(plans).where(plans.c.code == "starter").values(
            tagline="לעסק שמתחיל לעבוד עם מקור מכירות אחד",
            recommended=False,
            features=[
                "לוח בקרה ותמונת הכנסות מלאה",
                "רשימת מכירות וחיפוש",
                "ייבוא מכירות מקובץ CSV",
                "מרכז ״דורש טיפול״",
                "פניות לתמיכה",
            ],
        )
    )
    op.execute(
        sa.update(plans).where(plans.c.code == "business").values(
            tagline="המסלול המומלץ לרוב העסקים",
            recommended=True,
        )
    )
    op.execute(
        sa.update(plans).where(plans.c.code == "pro").values(
            tagline="לעסק שמוכר דרך כמה מקורות מכירה",
        )
    )
