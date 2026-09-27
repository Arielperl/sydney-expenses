"""Who may do what with payments, expressed in Sydney's existing roles.

Business roles (``business_members.role``): owner, manager, viewer.
Platform roles (``app_accounts.system_role``): user, support, admin, superadmin.

* owner    — view, create, cancel, refund
* manager  — view, create
* viewer   — view
* support  — nothing: support staff never charge, cancel, refund or see payment data
* admin / superadmin — no business payment actions by virtue of the platform
  role alone. They get ``PaymentAction.ADMIN_VIEW`` (a redacted, read-only
  projection without provider identifiers) for oversight; if they are also a
  member of the business, their business role applies to that business.

There is no business-level "admin" role in the current model; ``owner`` is
the role that holds full control.
"""

import enum
from dataclasses import dataclass


class PaymentAction(str, enum.Enum):
    VIEW = "view"
    CREATE = "create"
    CANCEL = "cancel"
    REFUND = "refund"
    ADMIN_VIEW = "admin_view"


BUSINESS_ROLE_PERMISSIONS: dict[str, frozenset[PaymentAction]] = {
    "owner": frozenset({PaymentAction.VIEW, PaymentAction.CREATE, PaymentAction.CANCEL, PaymentAction.REFUND}),
    "manager": frozenset({PaymentAction.VIEW, PaymentAction.CREATE}),
    "viewer": frozenset({PaymentAction.VIEW}),
}
PLATFORM_ADMIN_ROLES = frozenset({"admin", "superadmin"})


@dataclass(frozen=True)
class PaymentActor:
    user_id: str
    business_id: str
    business_role: str | None
    system_role: str = "user"


class PaymentPermissionError(Exception):
    pass


def is_allowed(actor: PaymentActor, action: PaymentAction) -> bool:
    if actor.system_role == "support":
        return False
    if action == PaymentAction.ADMIN_VIEW:
        return actor.system_role in PLATFORM_ADMIN_ROLES
    if not actor.business_id or actor.business_role is None:
        return False
    return action in BUSINESS_ROLE_PERMISSIONS.get(actor.business_role, frozenset())


def authorize(actor: PaymentActor, action: PaymentAction) -> None:
    if not is_allowed(actor, action):
        raise PaymentPermissionError(f"Not allowed to {action.value} payments")


def actor_from_request_user(user: dict) -> PaymentActor:
    """Build an actor from the dict ``protect_workspace`` stores on ``request.state.user``."""
    return PaymentActor(
        user_id=user["id"],
        business_id=user.get("business_id") or "",
        business_role=user.get("role"),
        system_role=user.get("system_role") or "user",
    )
