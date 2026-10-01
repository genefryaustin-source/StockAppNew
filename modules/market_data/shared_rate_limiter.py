"""
modules/market_data/shared_rate_limiter.py

One rolling-window rate limiter PER API KEY, shared by every call site in
the running process -- not a fresh limiter built locally inside each
function that happens to talk to Polygon/Massive.

Why this exists: two different code paths call Polygon/Massive with the
same API key -- the per-symbol path (modules.market_data.providers.polygon)
and the bulk grouped-daily path (modules.market_data.grouped_daily_history_builder).
Each used to build and pace its own private limiter, with zero visibility
into what the other was doing against the *same* key at the *same* time.
Today literally every tenant falls back to one shared platform-wide
POLYGON_API_KEY (per-tenant keys are supported but none are configured
yet), so the combined call volume from both paths -- across every
tenant, every background job, and every live page load -- routinely blew
past the account's real per-minute cap even when each path looked
well-behaved in isolation. That's what was producing rate-limit errors on
nearly every single request in the grouped-daily bulk fetch.

get_rate_limiter(api_key) returns the one limiter instance for that exact
key string, creating it on first use (default 5 calls/min, matching
Polygon's free tier). Keying on the key value itself, rather than one
global singleton, means that once a tenant adds their OWN Polygon key,
their traffic automatically gets its own independent budget instead of
continuing to share the platform key's bucket -- no code change needed
when that happens, since it'll simply be a different dict entry.

Thread-safe: jobs in this app run as in-process background threads inside
the single Streamlit service, so multiple threads can legitimately be
calling the same limiter concurrently.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Optional

_registry_lock = threading.Lock()
_limiters: dict[str, "_SharedRateLimiter"] = {}

_DEFAULT_CALLS_PER_MINUTE = 5  # matches Polygon/Massive's free tier


class _SharedRateLimiter:
    """Rolling-window limiter: at most `calls_per_minute` calls in any
    60-second window, shared across every caller holding a reference to
    this same instance (i.e. everyone using the same API key). Paces
    calls proactively -- sleeps before going over the limit -- rather
    than firing as fast as possible and reacting only after a 429 comes
    back."""

    def __init__(self, calls_per_minute: int):
        self.calls_per_minute = max(1, calls_per_minute)
        self._call_times: deque = deque()
        self._lock = threading.Lock()

    def set_calls_per_minute(self, calls_per_minute: int) -> None:
        """Adjust the budget for this key in place -- e.g. after a plan
        upgrade -- without needing to restart the service or recreate the
        limiter (which would lose its rolling-window history)."""
        with self._lock:
            self.calls_per_minute = max(1, calls_per_minute)

    def wait_if_needed(self) -> None:
        """Blocks (sleeps) until there is room for one more call within
        the rolling 60-second window, then reserves that slot. Safe to
        call concurrently from multiple threads."""
        while True:
            with self._lock:
                now = time.monotonic()
                while self._call_times and now - self._call_times[0] > 60:
                    self._call_times.popleft()

                if len(self._call_times) < self.calls_per_minute:
                    self._call_times.append(now)
                    return

                sleep_for = 60 - (now - self._call_times[0]) + 0.1

            # Sleep outside the lock so other threads can make progress
            # (check their own slot, or free up expired entries) while
            # this one waits. We loop back and re-check rather than
            # assuming a slot will definitely be free afterward, since
            # another thread may have taken it in the meantime.
            if sleep_for > 0:
                time.sleep(sleep_for)


def get_rate_limiter(
    api_key: str,
    calls_per_minute: Optional[int] = None,
) -> "_SharedRateLimiter":
    """Returns the one shared limiter for this exact API key, creating it
    on first use.

    calls_per_minute:
      - On first use of a given key, sets that key's initial budget
        (falls back to _DEFAULT_CALLS_PER_MINUTE if omitted).
      - On later calls for an already-created key, explicitly passing a
        value updates that key's budget going forward (e.g. a caller that
        knows about a plan upgrade). Passing None (the default) leaves
        the existing configured value alone -- so callers that don't
        have an opinion (like the per-symbol path) never accidentally
        clobber a budget someone else configured.
    """
    key = api_key or "__no_key__"
    with _registry_lock:
        limiter = _limiters.get(key)
        if limiter is None:
            limiter = _SharedRateLimiter(
                calls_per_minute if calls_per_minute is not None else _DEFAULT_CALLS_PER_MINUTE
            )
            _limiters[key] = limiter
        elif calls_per_minute is not None:
            limiter.set_calls_per_minute(calls_per_minute)
        return limiter