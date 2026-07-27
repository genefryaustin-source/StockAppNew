"""
modules/forex/forex_executive_command_center.py

Phase 18F — Executive command center.

Coordinates decision engine, opportunity scanner, AI Deal Room, risk committee,
trade queue, constraints, monitoring, and execution readiness.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexExecutiveCommandCenter:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def dashboard(self, snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        snapshot = snapshot or {}

        from modules.forex.forex_decision_engine import get_forex_decision_engine
        from modules.forex.forex_opportunity_scanner import get_forex_opportunity_scanner
        from modules.forex.forex_risk_committee import get_forex_risk_committee
        from modules.forex.forex_ai_deal_room import get_forex_ai_deal_room
        from modules.forex.forex_portfolio_constraints import get_forex_portfolio_constraints
        from modules.forex.forex_real_time_monitor import get_forex_real_time_monitor
        from modules.forex.forex_operations_health_monitor import get_forex_operations_health_monitor

        decisions = get_forex_decision_engine(db=self.db).decisions(snapshot=snapshot)
        ranked = decisions.get("priority", {}).get("ranked_trades", [])
        opportunities = get_forex_opportunity_scanner(db=self.db).scan()
        risk_committee = get_forex_risk_committee(db=self.db).review_queue(ranked[:10], snapshot=snapshot)
        deal_room = get_forex_ai_deal_room(db=self.db).review_queue(ranked[:10], snapshot=snapshot)
        constraints = get_forex_portfolio_constraints(db=self.db).evaluate(snapshot=snapshot)
        monitor = get_forex_real_time_monitor(db=self.db).dashboard(snapshot=snapshot, trades=ranked[:10])
        ops = get_forex_operations_health_monitor(db=self.db).snapshot()

        approved = [
            r for r in risk_committee.get("reviews", [])
            if r.get("risk_committee_decision") == "APPROVE"
        ]

        return {
            "status": "READY",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "executive_summary": {
                "decision_count": len(ranked),
                "approved_count": len(approved),
                "top_trade": ranked[0] if ranked else {},
                "portfolio_constraints_approved": constraints.get("approved"),
                "operations_status": ops.get("status"),
            },
            "decision_engine": decisions,
            "opportunity_scanner": opportunities,
            "risk_committee": risk_committee,
            "ai_deal_room": deal_room,
            "trade_queue": ranked,
            "portfolio_constraints": constraints,
            "real_time_monitor": monitor,
            "execution_readiness": ops,
        }


_CENTER = None


def get_forex_executive_command_center(db: Optional[Any] = None) -> ForexExecutiveCommandCenter:
    global _CENTER
    if _CENTER is None or (db is not None and _CENTER.db is None):
        _CENTER = ForexExecutiveCommandCenter(db=db)
    return _CENTER
