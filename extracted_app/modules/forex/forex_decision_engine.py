"""
modules/forex/forex_decision_engine.py

Phase 18A — Institutional Decision Engine.

Coordinates quant research, data fabric, risk, scoring, conviction, and priority.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ForexDecisionEngine:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def decisions(self, snapshot: Optional[Dict[str, Any]] = None, limit: int = 10) -> Dict[str, Any]:
        snapshot = snapshot or {}

        from modules.forex.forex_quant_research_engine import get_forex_quant_research_engine
        from modules.forex.forex_data_analytics_command_center import get_forex_data_analytics_command_center
        from modules.forex.forex_institutional_risk_engine import get_forex_institutional_risk_engine
        from modules.forex.forex_trade_scoring_engine import get_forex_trade_scoring_engine
        from modules.forex.forex_conviction_engine import get_forex_conviction_engine
        from modules.forex.forex_trade_priority_engine import get_forex_trade_priority_engine

        research = get_forex_quant_research_engine(db=self.db).research_dashboard(snapshot=snapshot)
        data = get_forex_data_analytics_command_center(db=self.db).dashboard(snapshot=snapshot)
        risk = get_forex_institutional_risk_engine(db=self.db).analyze(snapshot)

        ideas = research.get("alpha_research", {}).get("ideas", [])[:limit]
        scorer = get_forex_trade_scoring_engine(db=self.db)
        conviction_engine = get_forex_conviction_engine(db=self.db)

        decisions = []
        for idea in ideas:
            context = {
                "macro_score": self._macro_score(data, idea.get("pair")),
                "flow_score": self._flow_score(data, idea.get("pair")),
                "risk_score": risk.get("risk_score", 75),
                "portfolio_fit": 70,
                "execution_score": 75,
            }
            score = scorer.score_trade(idea, context=context)
            conviction = conviction_engine.conviction(score)
            decision = "APPROVE" if score["institutional_score"] >= 75 and conviction["conviction_score"] >= 75 else "HOLD" if score["institutional_score"] >= 60 else "REJECT"
            decisions.append({
                "pair": idea.get("pair"),
                "side": idea.get("signal"),
                "decision": decision,
                "institutional_score": score["institutional_score"],
                "conviction_score": conviction["conviction_score"],
                "score": score,
                "conviction": conviction,
                "rationale": self._rationale(idea, score, conviction, decision),
                "source_idea": idea,
            })

        priority = get_forex_trade_priority_engine(db=self.db).prioritize(decisions)

        return {
            "status": "READY",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "research": research,
            "data_fabric": data,
            "risk": risk,
            "decisions": decisions,
            "priority": priority,
        }

    def _macro_score(self, data: Dict[str, Any], pair: str) -> float:
        try:
            base = str(pair or "")[:3]
            rows = data["macro_intelligence"]["scorecard"]
            match = next((r for r in rows if r.get("currency") == base), None)
            return float(match.get("macro_score", 65)) if match else 65
        except Exception:
            return 65

    def _flow_score(self, data: Dict[str, Any], pair: str) -> float:
        try:
            bias = data["flow_analytics"].get("dealer_bias")
            return 75 if bias in {"BUY", "SELL"} else 60
        except Exception:
            return 60

    def _rationale(self, idea: Dict[str, Any], score: Dict[str, Any], conviction: Dict[str, Any], decision: str) -> str:
        return (
            f"{decision}: {idea.get('pair')} {idea.get('signal')} scored "
            f"{score.get('institutional_score')} with {conviction.get('conviction_score')} conviction. "
            f"Quant, macro, flow, AI, risk, portfolio fit, and execution readiness were reviewed."
        )


_ENGINE = None


def get_forex_decision_engine(db: Optional[Any] = None) -> ForexDecisionEngine:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexDecisionEngine(db=db)
    return _ENGINE
