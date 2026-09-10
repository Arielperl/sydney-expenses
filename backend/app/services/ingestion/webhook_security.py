"""HMAC signature + timestamp verification for incoming webhooks.

Deliberately separate from the route so it's unit-testable without an HTTP
request, and so the exact signing scheme (timestamp + "." + raw body) is
defined in one place a demo/real caller and the verifier both use.
"""

import hashlib
import hmac
import time


def compute_signature(secret: str, timestamp: str, raw_body: bytes) -> str:
    message = timestamp.encode("utf-8") + b"." + raw_body
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify_signature(secret: str, timestamp: str, raw_body: bytes, provided_signature: str) -> bool:
    expected = compute_signature(secret, timestamp, raw_body)
    return hmac.compare_digest(expected, provided_signature)


def is_timestamp_fresh(timestamp: str, *, tolerance_seconds: float, now: float | None = None) -> bool:
    try:
        timestamp_value = float(timestamp)
    except ValueError:
        return False
    current = now if now is not None else time.time()
    return abs(current - timestamp_value) <= tolerance_seconds
