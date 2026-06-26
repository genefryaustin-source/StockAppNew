"""
modules/forex/forex_portfolio_attribution.py

Phase 11 portfolio attribution.
"""

from __future__ import annotations

from typing import Any, Dict


def _f(x, d=0.0):
    try:
        return float(x)
    except Exception:
        return d


class ForexPortfolioAttribution:
    def __init__(self, db=None):
        self.db = db

    def attribute(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        positions = snapshot.get("positions") or []
        perf = snapshot.get("performance") or {}
        realized = _f(perf.get("total_realized_pnl"))
        unrealized = _f(perf.get("total_unrealized_pnl"))
        by_pair = {}
        by_side = {"BUY": 0.0, "SELL": 0.0, "OTHER": 0.0}
        for p in positions:
            if not isinstance(p, dict):
                continue
            pair = p.get("pair") or p.get("symbol") or p.get("Symbol") or "UNKNOWN"
            pnl = _f(p.get("unrealized_pnl") or p.get("P/L"))
            side = str(p.get("side") or p.get("Side") or "OTHER").upper()
            by_pair[pair] = by_pair.get(pair, 0.0) + pnl
            by_side[side if side in by_side else "OTHER"] += pnl
        return {
            "realized_pnl": round(realized, 2),
            "unrealized_pnl": round(unrealized, 2),
            "total_pnl": round(realized + unrealized, 2),
            "by_pair": by_pair,
            "by_side": by_side,
            "carry_return": 0.0,
            "translation_impact": 0.0,
            "alpha_component": round((realized + unrealized) * 0.65, 2),
            "beta_component": round((realized + unrealized) * 0.35, 2),
        }


_ATTR = None


def get_forex_portfolio_attribution(db=None):
    global _ATTR
    if _ATTR is None or (db is not None and _ATTR.db is None):
        _ATTR = ForexPortfolioAttribution(db=db)
    return _ATTR
