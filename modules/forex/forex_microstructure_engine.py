"""
modules/forex/forex_microstructure_engine.py

Market microstructure dashboard facade.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexMicrostructureEngine:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def dashboard(self, pair: str = "EUR/USD", **kwargs) -> Dict[str, Any]:
        from modules.forex.forex_market_depth import get_forex_market_depth

        depth = get_forex_market_depth(db=self.db).depth(pair=pair)
        return {
            "status": "READY",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "pair": pair,
            "depth": depth,
            "spread_monitor": {
                "spread": depth.get("spread"),
                "state": "NORMAL" if float(depth.get("spread") or 0) < (0.03 if "JPY" in pair else 0.0005) else "WIDE",
            },
            "session_tracker": self._session_state(),
            "liquidity_heatmap": self._heatmap(depth),
            "correlation_matrix": self._correlations(),
        }

    def _session_state(self):
        hour = datetime.now(timezone.utc).hour
        if 7 <= hour <= 16:
            session = "London / New York"
        elif 0 <= hour <= 7:
            session = "Asia"
        else:
            session = "New York Close"
        return {"session": session, "utc_hour": hour}

    def _heatmap(self, depth: Dict[str, Any]):
        return [
            {"bucket": "Top of Book", "liquidity_score": depth.get("depth_score", 0)},
            {"bucket": "Bid Imbalance", "liquidity_score": max(0, 50 + float(depth.get("liquidity_imbalance_pct") or 0))},
            {"bucket": "Ask Imbalance", "liquidity_score": max(0, 50 - float(depth.get("liquidity_imbalance_pct") or 0))},
        ]

    def _correlations(self):
        return [
            {"pair_a": "EUR/USD", "pair_b": "GBP/USD", "correlation": 0.78},
            {"pair_a": "AUD/USD", "pair_b": "NZD/USD", "correlation": 0.84},
            {"pair_a": "USD/JPY", "pair_b": "USD/CHF", "correlation": 0.42},
        ]


_MICRO = None


def get_forex_microstructure_engine(db: Optional[Any] = None) -> ForexMicrostructureEngine:
    global _MICRO
    if _MICRO is None or (db is not None and _MICRO.db is None):
        _MICRO = ForexMicrostructureEngine(db=db)
    return _MICRO
