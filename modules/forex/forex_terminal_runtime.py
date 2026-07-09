"""
modules/forex/forex_terminal_runtime.py

Sprint 26
Phase 2

Unified Forex Terminal Runtime

This becomes the single entry point for every Forex UI.

Trading Desk
Portfolio Dashboard
Risk Dashboard
Performance Dashboard
Execution Center
Institutional Dashboard

ALL consume the same runtime snapshot.

No UI.
No Streamlit.
No database queries outside the Snapshot Builder.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from modules.forex.forex_terminal_snapshot_builder import (
    get_forex_terminal_snapshot_builder,
)

from modules.forex.forex_terminal_snapshot_models import (
    ForexTerminalSnapshot,
)


# =====================================================================
# helpers
# =====================================================================

def _utc_now():
    return datetime.now(timezone.utc)


# =====================================================================
# Runtime
# =====================================================================

class ForexTerminalRuntime:

    """
    Institutional runtime.

    Owns exactly ONE snapshot.

    All dashboards consume this runtime.
    """

    def __init__(
        self,
        *,
        db=None,
    ):

        self.db = db

        self.runtime_id = uuid.uuid4().hex[:8]

        self.generated_at = None

        self.snapshot_cache: Optional[
            ForexTerminalSnapshot
        ] = None

        self.cache_key = None

        self.runtime_ms = 0.0

    # =================================================================

    def snapshot(
        self,
        *,
        tenant_id,
        user_id,
        portfolio_id,
        refresh=False,
        persist=False,
    ) -> ForexTerminalSnapshot:

        cache_key = (

            tenant_id,

            user_id,

            portfolio_id,

        )

        if (

            not refresh

            and self.snapshot_cache is not None

            and cache_key == self.cache_key

        ):

            return self.snapshot_cache

        builder = get_forex_terminal_snapshot_builder(

            db=self.db,

            runtime=self,

        )

        snapshot = builder.build(

            tenant_id=tenant_id,

            user_id=user_id,

            portfolio_id=portfolio_id,

            refresh=refresh,

            persist=persist,

        )

        self.snapshot_cache = snapshot

        self.cache_key = cache_key

        self.generated_at = _utc_now()

        return snapshot

    # =================================================================

    def refresh(
        self,
        *,
        tenant_id,
        user_id,
        portfolio_id,
    ) -> ForexTerminalSnapshot:

        return self.snapshot(

            tenant_id=tenant_id,

            user_id=user_id,

            portfolio_id=portfolio_id,

            refresh=True,

            persist=True,

        )

    # =================================================================

    def invalidate(self):

        self.snapshot_cache = None

        self.cache_key = None

    # =================================================================

    @property
    def has_snapshot(self):

        return self.snapshot_cache is not None

    # =================================================================

    @property
    def snapshot_object(self):

        return self.snapshot_cache

    # =================================================================

    def account(self):

        if self.snapshot_cache is None:

            return None

        return self.snapshot_cache.account

    # =================================================================

    def portfolio(self):

        if self.snapshot_cache is None:

            return None

        return self.snapshot_cache.portfolio

    # =================================================================

    def positions(self):

        if self.snapshot_cache is None:

            return []

        return self.snapshot_cache.positions

    # =================================================================

    def open_orders(self):

        if self.snapshot_cache is None:

            return []

        return self.snapshot_cache.open_orders

    # =================================================================

    def filled_orders(self):

        if self.snapshot_cache is None:

            return []

        return self.snapshot_cache.filled_orders

    # =================================================================

    def executions(self):

        if self.snapshot_cache is None:

            return []

        return self.snapshot_cache.executions

    # =================================================================

    def performance(self):

        if self.snapshot_cache is None:

            return None

        return self.snapshot_cache.performance

    # =================================================================

    def risk(self):

        if self.snapshot_cache is None:

            return None

        return self.snapshot_cache.risk

    # =================================================================

    def exposure(self):

        if self.snapshot_cache is None:

            return None

        return self.snapshot_cache.exposure

    # =================================================================

    def provider_health(self):

        if self.snapshot_cache is None:

            return None

        return self.snapshot_cache.provider_health

    # =================================================================

    def diagnostics(self):

        if self.snapshot_cache is None:

            return None

        return self.snapshot_cache.diagnostics

    # =================================================================

    def executive_ai(self):

        if self.snapshot_cache is None:

            return {}

        return self.snapshot_cache.executive_ai

    # =================================================================

    def strategy(self):

        if self.snapshot_cache is None:

            return {}

        return self.snapshot_cache.strategy

    # =================================================================

    def system(self):

        if self.snapshot_cache is None:

            return {}

        return self.snapshot_cache.system

    # =================================================================

    def metadata(self):

        if self.snapshot_cache is None:

            return {}

        return self.snapshot_cache.metadata

    # =================================================================

    def to_dict(self):

        if self.snapshot_cache is None:

            return {}

        return self.snapshot_cache.to_dict()


# =====================================================================
# Singleton
# =====================================================================

_RUNTIME = None


def get_forex_terminal_runtime(
    *,
    db=None,
):

    global _RUNTIME

    if (

        _RUNTIME is None

        or _RUNTIME.db is not db

    ):

        _RUNTIME = ForexTerminalRuntime(

            db=db,

        )

    return _RUNTIME