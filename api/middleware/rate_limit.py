"""
api/middleware/rate_limit.py

Rate Limiting Middleware

Enforces PlatformAPIKey.rate_limit_per_minute -- which existed as a
stored field on every API key since api/auth/api_keys.py was built, but
nothing ever actually checked it. A rate limit that isn't enforced
doesn't protect against anything; this is what makes it real.

Design, and its honest limits
------------------------------
In-memory, per-process, sliding-window counters. This is deliberately
simple rather than Redis-backed, since nothing else in this codebase
uses an external cache/store -- adding one just for this would be a
bigger architectural change than "wire up the rate limit field that
already exists." Two consequences worth knowing:

  * Counters reset on process restart.
  * If this API ever runs as more than one worker process/replica
    behind a load balancer, each process enforces its own limit
    independently -- a caller could get up to (limit * worker_count)
    requests through in practice, not exactly `limit`. Fine for a
    single-process deployment; a real multi-worker production
    deployment under active attack would want a shared store (Redis
    INCR + EXPIRE is the standard approach) instead of this. Swapping
    the storage backend later doesn't require changing any caller of
    this middleware -- only _RateLimitStore's internals.

Bucketing
---------
Requests presenting X-API-Key are bucketed (and rate-limited) by that
key's own hash, using its own rate_limit_per_minute -- looked up from
the database, cached briefly (see _KeyLimitCache) so this doesn't
issue a database query on every single request. An unrecognized or
malformed key still gets its own bucket (bucketed by whatever string
was presented) at the default rate, so credential-guessing attempts are
throttled too, not just valid keys.

Requests without an API key (development mode, JWT-authenticated
requests, or anonymous requests to public endpoints) are bucketed by
client IP (X-Forwarded-For's first entry if present, else the direct
socket peer) at settings.requests_per_minute.

Health, docs, and OpenAPI endpoints are exempt -- monitoring/uptime
checks shouldn't compete with real traffic for a caller's quota, and
exempting them doesn't weaken protection against abuse of the actual
API surface.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.config import settings

logger = logging.getLogger(__name__)

_WINDOW_SECONDS = 60.0

# Paths exempt from rate limiting -- monitoring/uptime checks, not real
# API traffic.
_EXEMPT_PREFIXES = ("/health", "/docs", "/redoc", "/openapi.json")

# How long a looked-up key's rate limit is trusted before re-querying
# the database -- bounds both the extra DB load from checking on every
# request, and how long a just-changed or just-revoked key's new limit
# takes to apply.
_KEY_LIMIT_CACHE_TTL_SECONDS = 30.0


class _KeyLimitCache:
    """
    Tiny in-memory cache: API key hash -> (rate_limit_per_minute,
    cached_at). Avoids a database query on every single request just to
    find out what limit applies -- auth already does its own database
    lookup to validate the key; this is deliberately separate rather
    than piggybacking on that result, since middleware runs before
    routing/auth dependencies resolve.
    """

    def __init__(self):
        self._cache: dict[str, tuple[int, float]] = {}
        self._lock = Lock()

    def get_limit(self, raw_api_key: str) -> int:
        import hashlib

        key_hash = hashlib.sha256(raw_api_key.encode("utf-8")).hexdigest()

        now = time.monotonic()

        with self._lock:
            cached = self._cache.get(key_hash)
            if cached is not None and (now - cached[1]) < _KEY_LIMIT_CACHE_TTL_SECONDS:
                return cached[0]

        limit = self._lookup_from_db(key_hash)

        with self._lock:
            self._cache[key_hash] = (limit, now)

        return limit

    @staticmethod
    def _lookup_from_db(key_hash: str) -> int:
        try:
            from modules.db.core import new_db_session
            from modules.db.models import PlatformAPIKey

            db = new_db_session()
            try:
                record = (
                    db.query(PlatformAPIKey)
                    .filter(PlatformAPIKey.key_hash == key_hash)
                    .one_or_none()
                )
                if record is not None and record.is_active and record.revoked_at is None:
                    return record.rate_limit_per_minute
            finally:
                db.close()
        except Exception:
            logger.exception("Rate limit lookup failed; using default.")

        # Unrecognized/invalid/revoked key -- still gets a real limit
        # (not unlimited), just the conservative default rather than
        # whatever a valid key might be granted.
        return settings.requests_per_minute


class _RateLimitStore:
    """
    Per-bucket sliding-window request timestamps. One bucket per API
    key (by hash) or per IP.
    """

    def __init__(self):
        self._buckets: dict[str, deque] = {}
        self._lock = Lock()

    def check_and_record(self, bucket_key: str, limit: int) -> tuple[bool, int]:
        """
        Returns (allowed, retry_after_seconds). Records this request
        against the bucket only if it's allowed -- a rejected request
        doesn't count against the caller's own limit twice.
        """

        now = time.monotonic()
        cutoff = now - _WINDOW_SECONDS

        with self._lock:
            bucket = self._buckets.setdefault(bucket_key, deque())

            while bucket and bucket[0] < cutoff:
                bucket.popleft()

            if len(bucket) >= limit:
                retry_after = max(1, int(bucket[0] + _WINDOW_SECONDS - now) + 1)
                return False, retry_after

            bucket.append(now)
            return True, 0


_key_limit_cache = _KeyLimitCache()
_store = _RateLimitStore()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Enforces per-API-key (or per-IP, for non-API-key traffic) rate
    limits. Returns 429 with a Retry-After header when exceeded --
    constructed directly as a JSONResponse rather than by raising
    api.exceptions.TooManyRequests, so the rejection doesn't depend on
    how Starlette's version-specific exception propagation through
    BaseHTTPMiddleware behaves; this always produces the same
    response shape as the rest of the API's error responses either way.
    """

    async def dispatch(self, request: Request, call_next):

        path = request.url.path

        if any(path.startswith(p) for p in _EXEMPT_PREFIXES):
            return await call_next(request)

        api_key = request.headers.get("X-API-Key")

        if api_key:
            bucket_key = f"apikey:{api_key}"
            limit = _key_limit_cache.get_limit(api_key)
        else:
            bucket_key = f"ip:{_client_ip(request)}"
            limit = settings.requests_per_minute

        allowed, retry_after = _store.check_and_record(bucket_key, limit)

        if not allowed:
            logger.warning(
                "Rate limit exceeded | bucket=%s | limit=%s | path=%s",
                bucket_key.split(":", 1)[0] + ":***",
                limit,
                path,
            )

            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(retry_after)},
                content={
                    "success": False,
                    "request_id": getattr(request.state, "request_id", None),
                    "error": {
                        "code": "rate_limit",
                        "message": "Too Many Requests",
                        "details": {
                            "limit_per_minute": limit,
                            "retry_after_seconds": retry_after,
                        },
                    },
                },
            )

        return await call_next(request)