"""
modules/forex/forex_portfolio_cache.py

Sprint 26
Forex Portfolio Cache

Purpose
-------
Shared in-memory cache for all Forex portfolio-related data.

The cache prevents repeated database queries during a single
dashboard render and significantly reduces repeated calls such as:

    LOAD_POSITIONS
    LOAD_POSITIONS
    LOAD_POSITIONS

Features
--------
• Position cache
• Portfolio summary cache
• Open order cache
• Account cache
• Thread safe
• TTL expiration
• Automatic invalidation
• Runtime integration
"""

from __future__ import annotations

import threading
import time

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


DEFAULT_CACHE_TTL = 30.0


def utc_now():
    return datetime.now(timezone.utc)


def utc_iso():
    return utc_now().isoformat()


@dataclass(slots=True)
class CacheStatistics:

    hits: int = 0
    misses: int = 0
    refreshes: int = 0
    invalidations: int = 0

    position_requests: int = 0
    summary_requests: int = 0
    order_requests: int = 0
    account_requests: int = 0

    created_at: str = field(default_factory=utc_iso)

    @property
    def hit_rate(self):

        total = self.hits + self.misses

        if total == 0:
            return 0.0

        return round(self.hits / total * 100.0, 2)


@dataclass(slots=True)
class CacheEntry:

    value: Any

    created: float = field(default_factory=time.time)

    ttl: float = DEFAULT_CACHE_TTL

    refresh_count: int = 0

    def expired(self):

        return (time.time() - self.created) >= self.ttl

    def age(self):

        return round(time.time() - self.created, 3)

    def touch(self):

        self.created = time.time()
        self.refresh_count += 1


@dataclass(frozen=True, slots=True)
class CacheKey:

    tenant_id: Optional[str]

    user_id: Optional[str]

    portfolio_id: Optional[str]

    category: str

    def key(self):

        return (
            self.tenant_id,
            self.user_id,
            self.portfolio_id,
            self.category,
        )


class PortfolioCacheStore:

    """
    Internal cache dictionaries.

    The cache manager wraps this class so locking
    remains centralized.
    """

    def __init__(self):

        self.positions: Dict[Any, CacheEntry] = {}

        self.summary: Dict[Any, CacheEntry] = {}

        self.orders: Dict[Any, CacheEntry] = {}

        self.account: Dict[Any, CacheEntry] = {}

    def clear(self):

        self.positions.clear()

        self.summary.clear()

        self.orders.clear()

        self.account.clear()

    def size(self):

        return (
            len(self.positions)
            + len(self.summary)
            + len(self.orders)
            + len(self.account)
        )


class PortfolioCacheConfig:

    def __init__(

        self,

        ttl: float = DEFAULT_CACHE_TTL,

    ):

        self.ttl = float(ttl)


class PortfolioCacheBase:

    """
    Base cache object.

    ForexPortfolioCache extends this class in the
    next section.
    """

    def __init__(

        self,

        ttl: float = DEFAULT_CACHE_TTL,

    ):

        self._lock = threading.RLock()

        self.config = PortfolioCacheConfig(ttl)

        self.stats = CacheStatistics()

        self.store = PortfolioCacheStore()

        self.created_at = utc_iso()

    def cache_key(

        self,

        tenant_id,

        user_id,

        portfolio_id,

        category,

    ):

        return CacheKey(

            tenant_id,

            user_id,

            portfolio_id,

            category,

        ).key()

    def diagnostics(self):

        return {

            "created_at": self.created_at,

            "ttl": self.config.ttl,

            "entries": self.store.size(),

            "hit_rate": self.stats.hit_rate,

            "hits": self.stats.hits,

            "misses": self.stats.misses,

            "refreshes": self.stats.refreshes,

            "invalidations": self.stats.invalidations,

            "position_requests": self.stats.position_requests,

            "summary_requests": self.stats.summary_requests,

            "order_requests": self.stats.order_requests,

            "account_requests": self.stats.account_requests,

        }


# =====================================================================
# END OF SECTION 1
#
# NEXT:
#
# class ForexPortfolioCache(PortfolioCacheBase)
#
# Generic cache retrieval
# Generic cache insertion
# Position cache
# Portfolio summary cache
# Order cache
# Account cache
# =====================================================================
# =====================================================================
# CONTINUATION OF forex_portfolio_cache.py
#
# Continue immediately after PortfolioCacheBase
# DO NOT REPEAT IMPORTS
# =====================================================================


class ForexPortfolioCache(PortfolioCacheBase):
    """
    Shared runtime portfolio cache.

    The cache stores portfolio objects once per dashboard refresh
    and serves every downstream consumer from memory.

    This eliminates repeated:

        LOAD_POSITIONS
        LOAD_POSITIONS
        LOAD_POSITIONS

    during a single render cycle.
    """

    def __init__(
        self,
        ttl: float = DEFAULT_CACHE_TTL,
    ):
        super().__init__(ttl=ttl)

    # ---------------------------------------------------------
    # Generic Cache Helpers
    # ---------------------------------------------------------

    def _lookup(
        self,
        cache: Dict[Any, CacheEntry],
        key,
    ):
        entry = cache.get(key)

        if entry is None:

            self.stats.misses += 1

            return None

        if entry.expired():

            cache.pop(key, None)

            self.stats.misses += 1

            return None

        self.stats.hits += 1

        return entry.value

    def _store(
        self,
        cache: Dict[Any, CacheEntry],
        key,
        value,
    ):

        cache[key] = CacheEntry(

            value=value,

            ttl=self.config.ttl,

        )

        self.stats.refreshes += 1

        return value

    # ---------------------------------------------------------
    # Positions
    # ---------------------------------------------------------

    def get_positions(

        self,

        tenant_id,

        user_id,

        portfolio_id,

    ):

        self.stats.position_requests += 1

        key = self.cache_key(

            tenant_id,

            user_id,

            portfolio_id,

            "positions",

        )

        with self._lock:

            return self._lookup(

                self.store.positions,

                key,

            )

    def set_positions(

        self,

        tenant_id,

        user_id,

        portfolio_id,

        positions,

    ):

        key = self.cache_key(

            tenant_id,

            user_id,

            portfolio_id,

            "positions",

        )

        with self._lock:

            return self._store(

                self.store.positions,

                key,

                positions,

            )

    # ---------------------------------------------------------
    # Portfolio Summary
    # ---------------------------------------------------------

    def get_summary(

        self,

        tenant_id,

        user_id,

        portfolio_id,

    ):

        self.stats.summary_requests += 1

        key = self.cache_key(

            tenant_id,

            user_id,

            portfolio_id,

            "summary",

        )

        with self._lock:

            return self._lookup(

                self.store.summary,

                key,

            )

    def set_summary(

        self,

        tenant_id,

        user_id,

        portfolio_id,

        summary,

    ):

        key = self.cache_key(

            tenant_id,

            user_id,

            portfolio_id,

            "summary",

        )

        with self._lock:

            return self._store(

                self.store.summary,

                key,

                summary,

            )

    # ---------------------------------------------------------
    # Orders
    # ---------------------------------------------------------

    def get_orders(

        self,

        tenant_id,

        user_id,

        portfolio_id,

    ):

        self.stats.order_requests += 1

        key = self.cache_key(

            tenant_id,

            user_id,

            portfolio_id,

            "orders",

        )

        with self._lock:

            return self._lookup(

                self.store.orders,

                key,

            )

    def set_orders(

        self,

        tenant_id,

        user_id,

        portfolio_id,

        orders,

    ):

        key = self.cache_key(

            tenant_id,

            user_id,

            portfolio_id,

            "orders",

        )

        with self._lock:

            return self._store(

                self.store.orders,

                key,

                orders,

            )

    # ---------------------------------------------------------
    # Account
    # ---------------------------------------------------------

    def get_account(

        self,

        tenant_id,

        user_id,

        portfolio_id,

    ):

        self.stats.account_requests += 1

        key = self.cache_key(

            tenant_id,

            user_id,

            portfolio_id,

            "account",

        )

        with self._lock:

            return self._lookup(

                self.store.account,

                key,

            )

    def set_account(

        self,

        tenant_id,

        user_id,

        portfolio_id,

        account,

    ):

        key = self.cache_key(

            tenant_id,

            user_id,

            portfolio_id,

            "account",

        )

        with self._lock:

            return self._store(

                self.store.account,

                key,

                account,

            )

# =====================================================================
# END OF SECTION 2
#
# NEXT SECTION
#
# Cache invalidation
# Force refresh
# Runtime integration
# Session Manager integration
# Database Profiler integration
# Singleton
# Public helper functions
#
# This will complete forex_portfolio_cache.py
# =====================================================================
# =====================================================================
# CONTINUATION OF forex_portfolio_cache.py
#
# Continue immediately after Section 2
# DO NOT REPEAT IMPORTS
# =====================================================================

    # ---------------------------------------------------------
    # Cache Invalidation
    # ---------------------------------------------------------

    def invalidate_positions(
        self,
        tenant_id=None,
        user_id=None,
        portfolio_id=None,
    ):
        key = self.cache_key(
            tenant_id,
            user_id,
            portfolio_id,
            "positions",
        )

        with self._lock:
            self.store.positions.pop(key, None)
            self.stats.invalidations += 1

    def invalidate_summary(
        self,
        tenant_id=None,
        user_id=None,
        portfolio_id=None,
    ):
        key = self.cache_key(
            tenant_id,
            user_id,
            portfolio_id,
            "summary",
        )

        with self._lock:
            self.store.summary.pop(key, None)
            self.stats.invalidations += 1

    def invalidate_orders(
        self,
        tenant_id=None,
        user_id=None,
        portfolio_id=None,
    ):
        key = self.cache_key(
            tenant_id,
            user_id,
            portfolio_id,
            "orders",
        )

        with self._lock:
            self.store.orders.pop(key, None)
            self.stats.invalidations += 1

    def invalidate_account(
        self,
        tenant_id=None,
        user_id=None,
        portfolio_id=None,
    ):
        key = self.cache_key(
            tenant_id,
            user_id,
            portfolio_id,
            "account",
        )

        with self._lock:
            self.store.account.pop(key, None)
            self.stats.invalidations += 1

    def invalidate_portfolio(
        self,
        tenant_id=None,
        user_id=None,
        portfolio_id=None,
    ):
        """
        Remove every cached object belonging to a portfolio.
        """

        self.invalidate_positions(
            tenant_id,
            user_id,
            portfolio_id,
        )

        self.invalidate_summary(
            tenant_id,
            user_id,
            portfolio_id,
        )

        self.invalidate_orders(
            tenant_id,
            user_id,
            portfolio_id,
        )

        self.invalidate_account(
            tenant_id,
            user_id,
            portfolio_id,
        )

    def invalidate_all(self):
        with self._lock:
            self.store.clear()
            self.stats.invalidations += 1

    # ---------------------------------------------------------
    # Force Refresh Helpers
    # ---------------------------------------------------------

    def refresh_positions(
        self,
        tenant_id,
        user_id,
        portfolio_id,
        loader,
    ):
        positions = loader()

        self.set_positions(
            tenant_id,
            user_id,
            portfolio_id,
            positions,
        )

        return positions

    def refresh_summary(
        self,
        tenant_id,
        user_id,
        portfolio_id,
        loader,
    ):
        summary = loader()

        self.set_summary(
            tenant_id,
            user_id,
            portfolio_id,
            summary,
        )

        return summary

    def refresh_orders(
        self,
        tenant_id,
        user_id,
        portfolio_id,
        loader,
    ):
        orders = loader()

        self.set_orders(
            tenant_id,
            user_id,
            portfolio_id,
            orders,
        )

        return orders

    def refresh_account(
        self,
        tenant_id,
        user_id,
        portfolio_id,
        loader,
    ):
        account = loader()

        self.set_account(
            tenant_id,
            user_id,
            portfolio_id,
            account,
        )

        return account

    # ---------------------------------------------------------
    # Runtime Integration
    # ---------------------------------------------------------

    def populate_runtime(
        self,
        runtime,
        tenant_id=None,
        user_id=None,
        portfolio_id=None,
    ):
        """
        Populate runtime with cached objects when available.
        """

        if runtime is None:
            return None

        runtime.positions = self.get_positions(
            tenant_id,
            user_id,
            portfolio_id,
        )

        runtime.portfolio = self.get_summary(
            tenant_id,
            user_id,
            portfolio_id,
        )

        runtime.orders = self.get_orders(
            tenant_id,
            user_id,
            portfolio_id,
        )

        runtime.account = self.get_account(
            tenant_id,
            user_id,
            portfolio_id,
        )

        return runtime

    # ---------------------------------------------------------
    # Diagnostics
    # ---------------------------------------------------------

    def summary(self):

        data = self.diagnostics()

        data.update({

            "position_cache": len(self.store.positions),

            "summary_cache": len(self.store.summary),

            "order_cache": len(self.store.orders),

            "account_cache": len(self.store.account),

        })

        return data


# =====================================================================
# Singleton
# =====================================================================

_CACHE = None


def get_forex_portfolio_cache(
    ttl=DEFAULT_CACHE_TTL,
):
    global _CACHE

    if _CACHE is None:

        _CACHE = ForexPortfolioCache(
            ttl=ttl,
        )

    return _CACHE


# =====================================================================
# Convenience Functions
# =====================================================================

def clear_forex_portfolio_cache():

    get_forex_portfolio_cache().invalidate_all()


def forex_portfolio_cache_summary():

    return get_forex_portfolio_cache().summary()


# =====================================================================
# END OF MODULE
# =====================================================================
