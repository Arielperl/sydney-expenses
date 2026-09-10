"""Business-calendar time — the single place "today", "this month", and any
other calendar-day computation is derived, always anchored to this demo
business's configured timezone (`app.domain.demo_business.DEMO_TIMEZONE`),
never the server process's own OS timezone and never a bare UTC "today".

Why this matters: Israel is UTC+2/+3, so for roughly the first two-to-three
hours after local midnight, UTC is still on the *previous* calendar day. A
naive `datetime.now(timezone.utc).date()` (or an OS-local `date.today()` on
a server not itself configured for Israel time) used as "today" during that
window disagrees with the business's own calendar — a sale a human just
created "today" in Israel can look like it's dated in the future relative
to that wrong "today", and gets rejected. Every business-calendar
computation in this app — sale-date validation, "today", current/previous
month dashboard boundaries, revenue trends, the assistant's relative-date
resolution, and any date filter meant to carry business-calendar meaning —
must go through one of the functions below instead of reaching for
`date.today()` / `datetime.utcnow()` / `datetime.now(timezone.utc)` itself.

Naive-timestamp convention: a timestamp with no `tzinfo` is interpreted as
already being business-local wall-clock time (Asia/Jerusalem) — never UTC.
This is the convention every naive timestamp actually flowing through this
app already follows in practice: a human filling in a sale date thinks in
their own local calendar, not UTC; a CSV bank-statement date column carries
no timezone at all; and `Sale.occurred_at` is written and read the same way
everywhere. A timezone-AWARE input (e.g. a webhook payload with an explicit
UTC offset) is converted with `.astimezone(...)` to the business timezone
instead, so an aware and a naive timestamp representing the same real-world
instant land on the same business calendar date. Ingestion boundaries that
accept an aware timestamp (see `app.services.ingestion.webhook_provider`)
normalize it to naive business-local time before it's ever persisted, so
every `Sale.occurred_at` value already stored is naive business-local —
comparing it against another naive business-local boundary (e.g. a month's
start/end) is always correct without any further conversion.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.domain.demo_business import DEMO_TIMEZONE

BUSINESS_TIMEZONE = ZoneInfo(DEMO_TIMEZONE)


def business_now() -> datetime:
    """The current instant, as an aware datetime in the business timezone."""
    return datetime.now(BUSINESS_TIMEZONE)


def business_today() -> date:
    """"Today" on the business's own calendar. Never derive "today" any
    other way for anything with business-calendar meaning."""
    return business_now().date()


def business_now_naive() -> datetime:
    """The current instant as naive business-local wall-clock time — for a
    column default whose value will be compared against other naive
    business-local timestamps (e.g. `Sale.occurred_at`'s fallback default).
    Audit-only timestamps (`created_at`/`updated_at`) are deliberately NOT
    switched to this — they stay plain UTC, since they carry no
    business-calendar meaning and unambiguous UTC ordering is what an audit
    trail actually wants."""
    return business_now().replace(tzinfo=None)


def to_business_datetime(value: datetime) -> datetime:
    """Interprets `value` per the naive-timestamp convention documented
    above and returns an aware datetime in the business timezone."""
    if value.tzinfo is None:
        return value.replace(tzinfo=BUSINESS_TIMEZONE)
    return value.astimezone(BUSINESS_TIMEZONE)


def business_date_of(value: datetime) -> date:
    """The business-calendar date a given timestamp falls on."""
    return to_business_datetime(value).date()


def normalize_to_naive_business_datetime(value: datetime) -> datetime:
    """Converts a possibly-aware provider timestamp to naive business-local
    wall-clock time, for storage. Use this exactly once, at the ingestion
    boundary of any source that might hand us a timezone-aware timestamp
    (a webhook payload, say) — never on a value already read back from the
    database, which is naive business-local already."""
    return to_business_datetime(value).replace(tzinfo=None)
