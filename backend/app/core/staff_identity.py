"""Public staff login names and their private Supabase email representation."""

import re

STAFF_LOGIN_SUFFIX = "@support"
STAFF_AUTH_SUFFIX = "@support.sydneyexpenses.com"
_STAFF_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{1,62}[a-z0-9]$")


def is_regular_email(value: str) -> bool:
    if "@" not in value:
        return False
    local, domain = value.rsplit("@", 1)
    return bool(local and "." in domain and not domain.startswith(".") and not domain.endswith("."))


def normalize_staff_login(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized.endswith(STAFF_LOGIN_SUFFIX):
        raise ValueError("שם ההתחברות צריך להסתיים ב־@support")
    name = normalized[: -len(STAFF_LOGIN_SUFFIX)]
    if not _STAFF_NAME.fullmatch(name):
        raise ValueError("שם ההתחברות צריך להכיל 3–64 תווים באנגלית, מספרים, נקודה, מקף או קו תחתון")
    return f"{name}{STAFF_LOGIN_SUFFIX}"


def is_staff_login(value: str) -> bool:
    try:
        normalize_staff_login(value)
    except ValueError:
        return False
    return True


def staff_auth_email(value: str) -> str:
    """Map a public `name@support` login to the valid email Supabase requires."""
    login = normalize_staff_login(value)
    return f"{login[: -len(STAFF_LOGIN_SUFFIX)]}{STAFF_AUTH_SUFFIX}"


def public_staff_login(value: str) -> str:
    normalized = value.strip().lower()
    if normalized.endswith(STAFF_AUTH_SUFFIX):
        return f"{normalized[: -len(STAFF_AUTH_SUFFIX)]}{STAFF_LOGIN_SUFFIX}"
    return normalized
