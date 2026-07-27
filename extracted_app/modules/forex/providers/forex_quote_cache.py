"""
modules/forex/providers/forex_quote_cache.py
"""

from __future__ import annotations

import threading
import time
from typing import Any, Optional


class ForexQuoteCache:
    """
    Shared Forex Quote Cache

    Sprint 29
    ----------
    * Runtime shared cache
    * TTL support
    * Cache hit/miss statistics
    * Automatic pruning

    TTL note (this session's freeze investigation):

    This was hardcoded to 15 seconds, which is far shorter than a single
    Institutional Terminal render actually takes. One page load fans out
    into many independent consumers that each ask the router for the same
    ~12-28 pairs -- refresh_positions(), the currency-strength ribbon, the
    institutional scanner's alpha run, daily_briefing()'s alpha run, the
    sentiment engine's alpha run, and the portfolio optimizer's alpha run --
    and real console captures showed each of these stages taking anywhere
    from a few hundred ms to several seconds on its own (several providers
    are currently broken or rate-limited: Finnhub throws JSONDecodeError,
    Alpha Vantage returns no usable rate, Polygon 429s and burns ~3-4s per
    pair before falling through). With a 15s TTL, by the time the 3rd or
    4th consumer in the same render asked for the same pairs, the cache
    had already expired -- forcing a full real refetch (again paying the
    slow-provider tax) multiple times within a single page load. That
    compounding is consistent with the multi-minute load times reported.

    Widening the TTL doesn't fabricate anything -- it's still a real,
    provider-sourced quote, just reused for a longer, still-short window
    instead of being needlessly refetched several times per render. 120s
    comfortably covers one render's worth of consumers while remaining a
    reasonable freshness window for a research/analysis terminal (any
    code path that needs a guaranteed-fresh quote at trade time should
    call with force_refresh=True rather than relying on this cache).
    """

    DEFAULT_TTL_SECONDS = 120
    MAX_CACHE_SIZE = 500

    def __init__(self, ttl_seconds: int | None = None):
        self.ttl_seconds = (
            ttl_seconds
            if ttl_seconds is not None
            else self.DEFAULT_TTL_SECONDS
        )

        self._lock = threading.RLock()

        self._cache: dict[str, dict[str, Any]] = {}

        self.cache_hits = 0
        self.cache_misses = 0

    def _key(self, pair: str) -> str:
        return (
            pair.upper()
            .replace("/", "")
            .replace("-", "")
        )

    def _expired(self, item: dict[str, Any]) -> bool:
        return (
            time.time() - item["timestamp"]
        ) > self.ttl_seconds

    def _prune(self) -> None:
        """
        Remove oldest cache entries if cache grows
        beyond MAX_CACHE_SIZE.
        """

        while len(self._cache) > self.MAX_CACHE_SIZE:

            oldest_key = min(
                self._cache,
                key=lambda k: self._cache[k]["timestamp"],
            )

            self._cache.pop(oldest_key, None)

    def is_fresh(
        self,
        pair: str,
    ) -> bool:

        key = self._key(pair)

        with self._lock:

            item = self._cache.get(key)

            if item is None:
                return False

            if self._expired(item):
                self._cache.pop(key, None)
                return False

            return True

    def get(
        self,
        pair: str,
    ) -> Optional[dict]:

        key = self._key(pair)

        with self._lock:

            item = self._cache.get(key)

            if item is None:
                self.cache_misses += 1
                return None

            if self._expired(item):
                self._cache.pop(key, None)
                self.cache_misses += 1
                return None

            self.cache_hits += 1

            return dict(item["value"])

    def put(
        self,
        pair: str,
        value: dict,
    ) -> dict:

        with self._lock:

            self._cache[self._key(pair)] = {
                "timestamp": time.time(),
                "value": dict(value),
            }

            self._prune()

        return value

    def invalidate(
        self,
        pair: str,
    ) -> None:

        with self._lock:
            self._cache.pop(
                self._key(pair),
                None,
            )

    def clear(self) -> None:

        with self._lock:
            self._cache.clear()

            self.cache_hits = 0
            self.cache_misses = 0

    def items(self):

        with self._lock:
            return list(self._cache.items())

    def __len__(self):

        with self._lock:
            return len(self._cache)

    def __iter__(self):

        with self._lock:
            return iter(dict(self._cache))

    def stats(self) -> dict:

        with self._lock:

            hit_rate = (
                self.cache_hits /
                (self.cache_hits + self.cache_misses)
                if (self.cache_hits + self.cache_misses)
                else 0.0
            )

            return {
                "entries": len(self._cache),
                "ttl_seconds": self.ttl_seconds,
                "max_cache_size": self.MAX_CACHE_SIZE,
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses,
                "hit_rate": round(hit_rate * 100, 2),
            }


_CACHE: ForexQuoteCache | None = None


def get_forex_quote_cache() -> ForexQuoteCache:
    global _CACHE

    if _CACHE is None:
        _CACHE = ForexQuoteCache()

    return _CACHE