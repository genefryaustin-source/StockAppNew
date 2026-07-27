"""
modules/forex/providers/forex_history_cache.py

Institutional TTL cache for Forex historical provider responses.

Sprint 25 Phase 4.5B-3:
- Cache history responses by pair + interval + date window
- Hit/miss counters
- Invalidation by pair, interval, or full cache
- Runtime diagnostics for dashboards and validation tools
"""

from __future__ import annotations

import sys
import threading
import time
from typing import Any, Optional


class ForexHistoryCache:
    def __init__(self, ttl_seconds: int = 60 * 60):
        self.ttl_seconds = int(ttl_seconds)
        self._lock = threading.RLock()
        self._cache: dict[str, dict[str, Any]] = {}
        self._hits = 0
        self._misses = 0
        self._puts = 0
        self._invalidations = 0

    @staticmethod
    def _clean_pair(pair: str) -> str:
        return str(pair or "").upper().replace("/", "").replace("-", "").replace("_", "").replace(" ", "")

    @staticmethod
    def _clean_interval(interval: str) -> str:
        return str(interval or "1day").lower().strip()

    @staticmethod
    def _clean_date(value: Any) -> str:
        if value is None:
            return ""
        return str(value)[:10]

    def _key(self, pair: str, interval: str, start_date: Any, end_date: Any) -> str:
        return (
            f"{self._clean_pair(pair)}:"
            f"{self._clean_interval(interval)}:"
            f"{self._clean_date(start_date)}:"
            f"{self._clean_date(end_date)}"
        )

    def get(
        self,
        pair: str,
        *,
        interval: str,
        start_date: Any,
        end_date: Any,
    ) -> Optional[dict[str, Any]]:
        key = self._key(pair, interval, start_date, end_date)

        with self._lock:
            item = self._cache.get(key)

            if not item:
                self._misses += 1
                return None

            age = time.time() - float(item.get("ts", 0))

            if age > self.ttl_seconds:
                self._cache.pop(key, None)
                self._misses += 1
                return None

            self._hits += 1
            value = dict(item.get("value") or {})
            value["cache_hit"] = True
            value["cache_key"] = key
            value["cache_age_seconds"] = round(age, 2)
            return value

    def put(
        self,
        pair: str,
        value: dict[str, Any],
        *,
        interval: str,
        start_date: Any,
        end_date: Any,
    ) -> dict[str, Any]:
        key = self._key(pair, interval, start_date, end_date)

        with self._lock:
            self._cache[key] = {
                "ts": time.time(),
                "value": dict(value or {}),
            }
            self._puts += 1

        return value

    def invalidate(
        self,
        pair: Optional[str] = None,
        *,
        interval: Optional[str] = None,
    ) -> int:
        pair_prefix = self._clean_pair(pair) if pair else None
        interval_clean = self._clean_interval(interval) if interval else None

        removed = 0

        with self._lock:
            for key in list(self._cache.keys()):
                parts = key.split(":")
                key_pair = parts[0] if len(parts) > 0 else ""
                key_interval = parts[1] if len(parts) > 1 else ""

                if pair_prefix and key_pair != pair_prefix:
                    continue

                if interval_clean and key_interval != interval_clean:
                    continue

                self._cache.pop(key, None)
                removed += 1

            self._invalidations += removed

        return removed

    def clear(self) -> None:
        with self._lock:
            removed = len(self._cache)
            self._cache.clear()
            self._invalidations += removed

    def prune_expired(self) -> int:
        removed = 0
        now = time.time()

        with self._lock:
            for key, item in list(self._cache.items()):
                age = now - float(item.get("ts", 0))
                if age > self.ttl_seconds:
                    self._cache.pop(key, None)
                    removed += 1

            self._invalidations += removed

        return removed

    def warm(self, items: list[dict[str, Any]]) -> int:
        loaded = 0

        for item in items:
            pair = item.get("pair")
            interval = item.get("interval") or "1day"
            start_date = item.get("start_date")
            end_date = item.get("end_date")
            value = item.get("value")

            if not pair or value is None:
                continue

            self.put(
                pair,
                value,
                interval=interval,
                start_date=start_date,
                end_date=end_date,
            )
            loaded += 1

        return loaded

    def stats(self) -> dict[str, Any]:
        with self._lock:
            total = self._hits + self._misses
            hit_rate = round(self._hits / total * 100, 2) if total else 0.0

            approx_bytes = 0
            try:
                approx_bytes = sys.getsizeof(self._cache)
                for key, value in self._cache.items():
                    approx_bytes += sys.getsizeof(key) + sys.getsizeof(value)
            except Exception:
                approx_bytes = 0

            rows = []
            now = time.time()
            for key, item in self._cache.items():
                value = item.get("value") or {}
                age = now - float(item.get("ts", 0))
                rows.append(
                    {
                        "key": key,
                        "provider": value.get("provider"),
                        "pair": value.get("pair"),
                        "interval": value.get("interval"),
                        "rows": len(value.get("rows") or []),
                        "age_seconds": round(age, 2),
                        "expired": age > self.ttl_seconds,
                    }
                )

            return {
                "entries": len(self._cache),
                "ttl_seconds": self.ttl_seconds,
                "hits": self._hits,
                "misses": self._misses,
                "puts": self._puts,
                "invalidations": self._invalidations,
                "hit_rate_pct": hit_rate,
                "approx_bytes": approx_bytes,
                "rows": rows,
            }


_CACHE: ForexHistoryCache | None = None


def get_forex_history_cache(ttl_seconds: int = 60 * 60) -> ForexHistoryCache:
    global _CACHE

    if _CACHE is None:
        _CACHE = ForexHistoryCache(ttl_seconds=ttl_seconds)

    return _CACHE
