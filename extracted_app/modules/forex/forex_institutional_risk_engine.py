"""
modules/forex/forex_institutional_risk_engine.py

Phase 11 institutional risk engine.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional


def _f(x, d=0.0):
    try:
        return float(x)
    except Exception:
        return d


class ForexInstitutionalRiskEngine:
    def __init__(self, db=None):
        self.db = db

    def analyze(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        account = snapshot.get("account") or {}
        positions = snapshot.get("positions") or []
        currency_exposure = snapshot.get("currency_exposure") or []
        pair_exposure = snapshot.get("pair_exposure") or []

        equity = _f(account.get("equity"))
        pnl_values = [_f(p.get("unrealized_pnl") or p.get("P/L")) for p in positions if isinstance(p, dict)]
        gross = sum(abs(_f(r.get("gross_notional") or r.get("gross_exposure"))) for r in pair_exposure if isinstance(r, dict))
        net = sum(_f(r.get("net_notional") or r.get("net_exposure")) for r in pair_exposure if isinstance(r, dict))

        stdev = self._stdev(pnl_values)
        var_95 = 1.65 * stdev
        cvar_95 = 2.06 * stdev
        gross_pct = gross / equity * 100 if equity else 0

        concentration = max([abs(_f(r.get("net_exposure_pct"))) for r in currency_exposure if isinstance(r, dict)] or [0])
        score = max(0, 100 - min(45, gross_pct * 0.05) - min(35, concentration * 0.15) - min(20, var_95 / max(equity, 1) * 100))

        return {
            "risk_score": round(score, 2),
            "value_at_risk_95": round(var_95, 2),
            "expected_shortfall_95": round(cvar_95, 2),
            "gross_exposure": round(gross, 2),
            "net_exposure": round(net, 2),
            "gross_exposure_pct": round(gross_pct, 4),
            "currency_concentration_pct": round(concentration, 4),
            "stress_tests": self.stress_tests(snapshot),
            "warnings": self._warnings(score, gross_pct, concentration),
        }

    def stress_tests(self, snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        equity = _f((snapshot.get("account") or {}).get("equity"))
        gross = sum(abs(_f(r.get("gross_notional") or r.get("gross_exposure"))) for r in snapshot.get("pair_exposure", []) if isinstance(r, dict))
        return [
            {"scenario": "USD shock +1%", "estimated_pnl": round(gross * -0.005, 2), "equity_after": round(equity - gross * 0.005, 2)},
            {"scenario": "Risk-off shock", "estimated_pnl": round(gross * -0.012, 2), "equity_after": round(equity - gross * 0.012, 2)},
            {"scenario": "Liquidity widening", "estimated_pnl": round(gross * -0.0025, 2), "equity_after": round(equity - gross * 0.0025, 2)},
        ]

    def _stdev(self, vals):
        if not vals:
            return 0.0
        mean = sum(vals) / len(vals)
        return math.sqrt(sum((x - mean) ** 2 for x in vals) / len(vals))

    def _warnings(self, score, gross_pct, concentration):
        out = []
        if score < 60:
            out.append("Risk score below institutional threshold.")
        if gross_pct > 300:
            out.append("Gross exposure above 3x equity.")
        if concentration > 150:
            out.append("Currency concentration above 150% of equity.")
        return out


_ENGINE = None


def get_forex_institutional_risk_engine(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexInstitutionalRiskEngine(db=db)
    return _ENGINE
