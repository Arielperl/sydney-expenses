"""Regression coverage for app.domain.business_time — in particular the
Israel-after-midnight-while-UTC-is-still-yesterday window that the demo
business's whole sale-date validation was previously getting wrong (see the
module's own docstring for why comparing against UTC or the server's OS
timezone is wrong here)."""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.domain import business_time
from app.domain.business_time import (
    business_date_of,
    business_today,
    normalize_to_naive_business_datetime,
    to_business_datetime,
)
from app.schemas.validators import validate_date_reasonable, validate_transaction_datetime_reasonable

# 2026-01-15 00:30 in Israel Standard Time (UTC+2, no DST in January) is
# still 2026-01-14 22:30 in UTC — the exact "after local midnight, UTC still
# on the previous calendar day" window this whole fix is about.
ISRAEL_JUST_AFTER_MIDNIGHT = datetime(2026, 1, 15, 0, 30, tzinfo=ZoneInfo("Asia/Jerusalem"))
UTC_STILL_PREVIOUS_DAY = ISRAEL_JUST_AFTER_MIDNIGHT.astimezone(timezone.utc)


@pytest.fixture
def frozen_israel_after_midnight(monkeypatch):
    """Pins `business_now()` to ISRAEL_JUST_AFTER_MIDNIGHT so this test
    doesn't depend on when it's actually run."""
    monkeypatch.setattr(business_time, "business_now", lambda: ISRAEL_JUST_AFTER_MIDNIGHT)
    yield


def test_utc_is_genuinely_still_the_previous_day():
    """Sanity check on the fixture itself, not the app: confirms the two
    instants really do fall on different UTC-vs-Israel calendar dates."""
    assert ISRAEL_JUST_AFTER_MIDNIGHT.date() == date(2026, 1, 15)
    assert UTC_STILL_PREVIOUS_DAY.date() == date(2026, 1, 14)


def test_business_today_is_the_israel_date_not_the_utc_date(frozen_israel_after_midnight):
    assert business_today() == date(2026, 1, 15)


def test_sale_dated_today_in_israel_is_not_rejected_as_future(frozen_israel_after_midnight):
    """The actual regression: a sale legitimately occurring "today" in
    Israel, right after local midnight, must not be rejected as a future
    transaction just because UTC's calendar hasn't rolled over yet."""
    today_in_israel = datetime(2026, 1, 15, 0, 15)  # naive — business-local, per convention
    assert validate_transaction_datetime_reasonable(today_in_israel) == today_in_israel


def test_a_genuinely_future_israeli_date_is_still_rejected(frozen_israel_after_midnight):
    tomorrow_in_israel = date(2026, 1, 16)
    with pytest.raises(ValueError, match="future"):
        validate_date_reasonable(tomorrow_in_israel)


def test_naive_timestamp_is_interpreted_as_already_business_local():
    naive = datetime(2026, 3, 10, 23, 0)
    aware = to_business_datetime(naive)
    assert aware.tzinfo is not None
    assert aware.replace(tzinfo=None) == naive  # no wall-clock shift for a naive input


def test_aware_utc_timestamp_is_converted_to_its_business_calendar_date():
    # 2026-03-10 23:00 UTC is 2026-03-11 01:00 in Israel (UTC+2 in March,
    # before that year's DST switch) — a different calendar day.
    aware_utc = datetime(2026, 3, 10, 23, 0, tzinfo=timezone.utc)
    assert business_date_of(aware_utc) == date(2026, 3, 11)


def test_normalize_strips_tzinfo_but_keeps_the_business_local_wall_clock_reading():
    aware_utc = datetime(2026, 3, 10, 23, 0, tzinfo=timezone.utc)
    normalized = normalize_to_naive_business_datetime(aware_utc)
    assert normalized.tzinfo is None
    assert normalized == datetime(2026, 3, 11, 1, 0)


def test_api_accepts_a_sale_dated_today_in_israel_after_midnight_while_utc_is_still_yesterday(
    client, frozen_israel_after_midnight
):
    """End-to-end regression: POSTing a manual sale at the exact moment
    this bug used to reject must succeed."""
    response = client.post(
        "/api/sales",
        json={
            "customer_name": "לקוחה לדוגמה",
            "service_name": "ייעוץ",
            "gross_amount": "100.00",
            "currency": "ILS",
            "occurred_at": "2026-01-15T00:15:00",
        },
    )
    assert response.status_code == 201, response.text
