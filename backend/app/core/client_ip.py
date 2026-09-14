"""Client-IP resolution for the Grow webhook's source-IP allowlist.

Grow's account-level webhook has no signing capability — `webhookKey` is
confirmed by Grow not to be a secret — so the connecting IP address is the
only application-layer defense available (see app/core/config.py's
`grow_webhook_allowed_ips`). That makes *which header is trustworthy* a real
security decision, not a convenience one; it must never be guessable/spoofable
by the request itself.

Verified against Vercel's own documentation
(https://vercel.com/docs/headers/request-headers, "x-forwarded-for" /
"x-vercel-forwarded-for" sections, fetched during this integration's
implementation): on a standard Vercel deployment, Vercel's edge network
overwrites `X-Forwarded-For` itself and does not forward whatever value a
client sent — "This restriction is in place to prevent IP spoofing." A
client-supplied `X-Forwarded-For` cannot survive to the function.
`X-Vercel-Forwarded-For` is documented as identical, except that it stays
reliable even if something *the project itself* puts in front of Vercel
(e.g. another CDN/proxy) were to alter `X-Forwarded-For` first — so this
module prefers it and falls back to `X-Forwarded-For` for local/non-Vercel
runs (`uvicorn --reload`), where neither header is set by anything and
`request.client.host` is used instead.

**Documented limitation, not silently ignored:** Vercel's Enterprise "Trusted
Proxy" feature explicitly allows a *custom* `X-Forwarded-For` value to pass
through unmodified for accounts that purchase and enable it. If this project
ever enables that feature, this header stops being trustworthy on its own and
this module's guarantee no longer holds — nothing in this codebase can detect
that from inside the function. See docs/security.md for this noted as a
standing production limitation.
"""

import ipaddress

from fastapi import Request

_IP_HEADERS = ("x-vercel-forwarded-for", "x-forwarded-for")


def resolve_client_ip(request: Request) -> str | None:
    """The best-available client IP for this request, per the trust
    ordering documented in the module docstring above."""
    for header in _IP_HEADERS:
        value = request.headers.get(header)
        if value:
            # A forwarded-for value is a comma-separated chain; the first
            # entry is the original client closest to the edge.
            first = value.split(",")[0].strip()
            if first:
                return first
    return request.client.host if request.client else None


def is_ip_allowed(client_ip: str | None, allowlist: list[str]) -> bool:
    """False whenever the allowlist is empty or the IP can't be parsed —
    this must fail closed, never open, on a misconfigured or malformed
    input (see validate_auth_settings, which refuses to start production
    with an empty allowlist at all)."""
    if not client_ip or not allowlist:
        return False
    try:
        address = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    for entry in allowlist:
        try:
            if address in ipaddress.ip_network(entry, strict=False):
                return True
        except ValueError:
            continue
    return False
