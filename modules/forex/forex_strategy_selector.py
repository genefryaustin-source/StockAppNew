"""
modules/forex/forex_strategy_selector.py

Phase 20A — Regime-aware strategy selector.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexStrategySelector:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def select(self, snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        snapshot = snapshot or {}
        regime = str((snapshot.get("market_overview") or {}).get("regime") or snapshot.get("regime") or "NEUTRAL").upper()
        if "RISK_OFF" in regime:
            selected = ["safe_haven_momentum", "usd_strength", "carry_reduction"]
        elif "RISK_ON" in regime:
            selected = ["high_beta_rotation", "carry_momentum", "trend_following"]
        else:
            selected = ["factor_momentum", "mean_reversion", "breakout_watch"]
        return {
            "status": "READY",
            "regime": regime,
            "selected_strategies": selected,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_ENGINE = None


def get_forex_strategy_selector(db: Optional[Any] = None) -> ForexStrategySelector:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexStrategySelector(db=db)
    return _ENGINE
