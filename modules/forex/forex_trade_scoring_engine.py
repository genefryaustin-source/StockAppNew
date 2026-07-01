"""
modules/forex/forex_trade_scoring_engine.py

Phase 18A — Institutional trade scoring engine.

Combines quantitative, macro, flow, AI, risk, and portfolio context into one
trade score suitable for institutional decision workflows.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


class ForexTradeScoringEngine:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def score_trade(self, trade: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        context = context or {}
        pair = trade.get("pair") or trade.get("symbol") or "EUR/USD"

        quant_score = _safe_float(trade.get("alpha_score") or trade.get("composite_factor_score") or trade.get("confidence"), 65)
        macro_score = _safe_float(context.get("macro_score") or trade.get("macro_score"), 65)
        flow_score = _safe_float(context.get("flow_score") or trade.get("flow_score"), 60)
        ai_score = _safe_float(trade.get("confidence") or context.get("ai_confidence"), 70)
        risk_score = _safe_float(context.get("risk_score"), 75)
        portfolio_fit = _safe_float(context.get("portfolio_fit"), 70)
        execution_score = _safe_float(context.get("execution_score"), 75)

        score = (
            quant_score * 0.22
            + macro_score * 0.16
            + flow_score * 0.14
            + ai_score * 0.18
            + risk_score * 0.14
            + portfolio_fit * 0.10
            + execution_score * 0.06
        )

        return {
            "status": "READY",
            "pair": pair,
            "side": trade.get("side") or trade.get("signal") or "WATCH",
            "institutional_score": round(score, 2),
            "quant_score": round(quant_score, 2),
            "macro_score": round(macro_score, 2),
            "flow_score": round(flow_score, 2),
            "ai_score": round(ai_score, 2),
            "risk_score": round(risk_score, 2),
            "portfolio_fit": round(portfolio_fit, 2),
            "execution_score": round(execution_score, 2),
            "decision_bias": "APPROVE" if score >= 75 else "HOLD" if score >= 60 else "REJECT",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_ENGINE = None


def get_forex_trade_scoring_engine(db: Optional[Any] = None) -> ForexTradeScoringEngine:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexTradeScoringEngine(db=db)
    return _ENGINE
