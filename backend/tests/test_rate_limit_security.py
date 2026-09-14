import pytest
from fastapi import HTTPException

from app.core.rate_limit import RateLimiter


def test_rate_limiter_sets_retry_after_header():
    limiter = RateLimiter(max_requests=1, window_seconds=12)
    limiter.check("same-client")

    with pytest.raises(HTTPException) as exc_info:
        limiter.check("same-client")

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers == {"Retry-After": "12"}


def test_rate_limiter_bounds_memory_for_attacker_controlled_keys():
    limiter = RateLimiter(max_requests=2, window_seconds=60, max_keys=3)

    for index in range(20):
        limiter.check(f"attacker-controlled-{index}")

    assert len(limiter._hits) <= 3
    assert len(limiter._last_seen) <= 3
