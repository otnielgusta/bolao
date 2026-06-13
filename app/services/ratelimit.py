"""Lightweight in-process rate limiter (fixed window per key).

Good enough for a single-process deployment. For multiple workers/instances,
back this with Redis instead — the API stays the same.
"""
import time

from fastapi import Request

_HITS: dict[str, list[float]] = {}


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def allow(key: str, limit: int, window_seconds: int) -> bool:
    """Record a hit for `key`. Returns False once `limit` is exceeded in window."""
    now = time.monotonic()
    cutoff = now - window_seconds
    bucket = _HITS.setdefault(key, [])
    while bucket and bucket[0] < cutoff:
        bucket.pop(0)
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True
