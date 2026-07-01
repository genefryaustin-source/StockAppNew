
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
    """

    DEFAULT_TTL_SECONDS = 15
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
