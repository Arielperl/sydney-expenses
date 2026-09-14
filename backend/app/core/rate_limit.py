"""A minimal in-process rate limiter for sensitive auth endpoints.

Deliberately in-memory rather than backed by Redis or another shared store:
this app runs as a single Uvicorn process (see README/deployment notes). That
makes this limiter a real, effective defense against a single attacker
hammering login/signup from one process — but a multi-process or
multi-instance production deployment (`uvicorn --workers N`, multiple
containers) would have one independent counter per process/instance, which a
determined attacker could spread requests across to multiply their effective
budget. A real horizontally-scaled deployment should replace this with a
shared store (e.g. Redis) keyed the same way. Documented here rather than
silently pretended away.
"""

import time
from collections import OrderedDict, deque
from math import ceil
from threading import Lock

from fastapi import HTTPException, Request

RATE_LIMIT_DETAIL = "יותר מדי ניסיונות. נסו שוב בעוד מספר דקות."


class RateLimiter:
    def __init__(self, *, max_requests: int, window_seconds: float, max_keys: int = 10_000):
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._max_keys = max_keys
        self._hits: dict[str, deque[float]] = {}
        self._last_seen: OrderedDict[str, float] = OrderedDict()
        self._lock = Lock()
        self._checks = 0

    def check(self, key: str) -> None:
        """Raises HTTP 429 if `key` has already hit the limit within the
        current window; otherwise records this attempt and returns."""
        now = time.monotonic()
        with self._lock:
            self._checks += 1
            if self._checks % 256 == 0:
                self._remove_expired_keys(now)
            hits = self._hits.get(key)
            if hits is None:
                if len(self._hits) >= self._max_keys:
                    oldest, _ = self._last_seen.popitem(last=False)
                    self._hits.pop(oldest, None)
                hits = self._hits[key] = deque()
            while hits and now - hits[0] > self._window_seconds:
                hits.popleft()
            self._last_seen[key] = now
            self._last_seen.move_to_end(key)
            if len(hits) >= self._max_requests:
                raise HTTPException(
                    status_code=429,
                    detail=RATE_LIMIT_DETAIL,
                    headers={"Retry-After": str(ceil(self._window_seconds))},
                )
            hits.append(now)

    def _remove_expired_keys(self, now: float) -> None:
        while self._last_seen:
            key, seen = next(iter(self._last_seen.items()))
            if now - seen <= self._window_seconds:
                break
            self._hits.pop(key, None)
            self._last_seen.pop(key, None)

    def reset(self) -> None:
        """Test-only: clears all recorded state between test cases."""
        with self._lock:
            self._hits.clear()
            self._last_seen.clear()
            self._checks = 0


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
