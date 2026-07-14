"""
modules/forex/forex_microstructure_engine.py

Market microstructure dashboard facade.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ForexMicrostructureEngine:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def dashboard(self, pair: str = "EUR/USD", **kwargs) -> Dict[str, Any]:
        from modules.forex.forex_market_depth import get_forex_market_depth

        depth = get_forex_market_depth(db=self.db).depth(pair=pair)
        spread = depth.get("spread")

        if spread is None:
            spread_state = "UNKNOWN"
        else:
            spread_state = "NORMAL" if float(spread) < (0.03 if "JPY" in pair else 0.0005) else "WIDE"

        return {
            "status": "READY",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "pair": pair,
            "depth": depth,
            "spread_monitor": {
                "spread": spread,
                "state": spread_state,
            },
            "session_tracker": self._session_state(),
            "liquidity_heatmap": self._heatmap(depth),
            "correlation_matrix": self._correlations(),
        }

    def _session_state(self) -> Dict[str, Any]:
        hour = datetime.now(timezone.utc).hour
        if 7 <= hour <= 16:
            session = "London / New York"
        elif 0 <= hour <= 7:
            session = "Asia"
        else:
            session = "New York Close"
        return {"session": session, "utc_hour": hour}

    def _heatmap(self, depth: Dict[str, Any]) -> List[Dict[str, Any]]:
        # depth_score / liquidity_imbalance_pct require an L2 feed that isn't
        # connected (see forex_market_depth.py) -- report honestly instead of
        # computing a heatmap out of None-defaulted-to-zero placeholders.
        if depth.get("depth_score") is None and depth.get("liquidity_imbalance_pct") is None:
            return [
                {"bucket": "Top of Book", "liquidity_score": None, "note": "No L2 feed connected."},
                {"bucket": "Bid Imbalance", "liquidity_score": None, "note": "No L2 feed connected."},
                {"bucket": "Ask Imbalance", "liquidity_score": None, "note": "No L2 feed connected."},
            ]
        imbalance = float(depth.get("liquidity_imbalance_pct") or 0)
        return [
            {"bucket": "Top of Book", "liquidity_score": depth.get("depth_score", 0)},
            {"bucket": "Bid Imbalance", "liquidity_score": max(0, 50 + imbalance)},
            {"bucket": "Ask Imbalance", "liquidity_score": max(0, 50 - imbalance)},
        ]

    def _correlations(self) -> List[Dict[str, Any]]:
        """
        Real pairwise FX correlations from forex_correlation_engine (computed
        from actual historical returns), replacing the previous hardcoded
        3-row table (EUR/USD-GBP/USD 0.78, etc.).
        """
        try:
            from modules.forex.forex_correlation_engine import get_forex_correlation_engine
            result = get_forex_correlation_engine(db=self.db).matrix()
        except Exception:
            return []

        if not isinstance(result, dict) or result.get("status") != "READY":
            return []

        pairs = result.get("pairs") or []
        matrix_rows = result.get("matrix") or []

        flat: List[Dict[str, Any]] = []
        seen = set()
        for row in matrix_rows:
            pair_a = row.get("pair")
            for pair_b in pairs:
                if pair_a == pair_b:
                    continue
                key = tuple(sorted([pair_a, pair_b]))
                if key in seen:
                    continue
                seen.add(key)
                value = row.get(pair_b)
                if value is None:
                    continue
                flat.append({"pair_a": pair_a, "pair_b": pair_b, "correlation": value})

        flat.sort(key=lambda r: abs(r["correlation"]), reverse=True)
        return flat[:10]


_MICRO = None


def get_forex_microstructure_engine(db: Optional[Any] = None) -> ForexMicrostructureEngine:
    global _MICRO
    if _MICRO is None or (db is not None and _MICRO.db is None):
        _MICRO = ForexMicrostructureEngine(db=db)
    return _MICRO