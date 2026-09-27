"""The plan catalog — the single server-side definition of what Sydney sells.

The migration seeds ``subscription_plans`` / ``subscription_plan_prices`` from
exactly these values, a test keeps the two in sync, and the frontend only
ever renders what ``GET /api/billing/plans`` returns. Prices are in agorot and
exclude VAT.

Only list a feature here if the product actually provides it. Member limits
are enforced but not advertised: the product has no way to add members to a
business yet (``MEMBER_INVITATIONS_AVAILABLE``), so advertising "up to five
members" would promise something that cannot be done.
"""

from dataclasses import dataclass

TRIAL_DAYS = 30
BILLING_CURRENCY = "ILS"
# Flip to True only when owners can actually invite members; the pricing page
# then starts showing the member limits automatically.
MEMBER_INVITATIONS_AVAILABLE = False


@dataclass(frozen=True)
class PlanDefinition:
    code: str
    name: str
    tagline: str
    sort_order: int
    recommended: bool
    monthly_price_minor: int
    yearly_price_minor: int
    max_connections: int
    max_members: int
    ai_questions_per_month: int
    features: tuple[str, ...]


_STARTER_FEATURES = (
    "לוח בקרה של הכנסות, מע״מ, עמלות וזיכויים",
    "פירוט המכירות ופרטי הלקוחות במקום אחד",
    "זיהוי עסקאות שנכשלו או שחסר בהן מידע",
    "עוזר עסקי שעונה על שאלות לפי נתוני המכירות",
)

PLANS: tuple[PlanDefinition, ...] = (
    PlanDefinition(
        code="starter",
        name="Starter",
        tagline="לעסק קטן שרוצה לראות ולנהל את ההכנסות במקום אחד",
        sort_order=1,
        recommended=True,
        monthly_price_minor=6_900,
        yearly_price_minor=69_000,
        max_connections=1,
        max_members=1,
        ai_questions_per_month=300,
        features=_STARTER_FEATURES,
    ),
    PlanDefinition(
        code="business",
        name="Business",
        tagline="לעסק שמקבל תשלומים מכמה מקומות",
        sort_order=2,
        recommended=False,
        monthly_price_minor=11_900,
        yearly_price_minor=119_000,
        max_connections=3,
        max_members=5,
        ai_questions_per_month=1_500,
        features=("כל מה שיש ב־Starter", "תמונה מאוחדת מכמה מקורות מכירה"),
    ),
    PlanDefinition(
        code="pro",
        name="Pro",
        tagline="לעסק עם פעילות רחבה ומספר מערכות מכירה",
        sort_order=3,
        recommended=False,
        monthly_price_minor=24_900,
        yearly_price_minor=249_000,
        max_connections=10,
        max_members=15,
        ai_questions_per_month=5_000,
        features=("כל מה שיש ב־Business", "מתאים לעסקים עם כמה מקורות מכירה"),
    ),
)

PLANS_BY_CODE = {plan.code: plan for plan in PLANS}
INTERVALS = ("month", "year")


def price_minor(plan: PlanDefinition, interval: str) -> int:
    if interval == "month":
        return plan.monthly_price_minor
    if interval == "year":
        return plan.yearly_price_minor
    raise ValueError("Unknown billing interval")


def seed_plan_catalog(db) -> None:
    """Insert the catalog into an empty database (tests, local dev). Production is seeded by the migration."""
    import uuid

    from app.billing.models import SubscriptionPlan, SubscriptionPlanPrice

    for plan in PLANS:
        if db.get(SubscriptionPlan, plan.code) is not None:
            continue
        db.add(SubscriptionPlan(
            code=plan.code, name=plan.name, tagline=plan.tagline, sort_order=plan.sort_order,
            recommended=plan.recommended, active=True, max_connections=plan.max_connections,
            max_members=plan.max_members, ai_questions_per_month=plan.ai_questions_per_month,
            priority_support=False, features=list(plan.features),
        ))
        db.flush()
        for interval in INTERVALS:
            db.add(SubscriptionPlanPrice(id=str(uuid.uuid4()), plan_code=plan.code, interval=interval,
                                         amount_minor=price_minor(plan, interval), currency=BILLING_CURRENCY))
    db.commit()
