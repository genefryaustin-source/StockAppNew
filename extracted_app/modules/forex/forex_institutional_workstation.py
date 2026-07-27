"""
modules/forex/forex_institutional_workstation.py

Phase 5 — Institutional Trading Workstation facade.

Combines trade ticket, AI trade assistant, risk manager, autonomous engine, and
execution monitor into one service for the dashboard/UI layer.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class ForexInstitutionalWorkstation:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def terminal_state(self, **kwargs) -> Dict[str, Any]:
        from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine
        from modules.forex.forex_ai_trade_assistant import get_forex_ai_trade_assistant
        from modules.forex.forex_institutional_risk_manager import get_forex_institutional_risk_manager
        from modules.forex.forex_execution_monitor import get_forex_execution_monitor

        engine = get_forex_portfolio_engine(
            tenant_id=kwargs.get("tenant_id"),
            user_id=kwargs.get("user_id"),
            portfolio_id=kwargs.get("portfolio_id"),
            db=self.db,
        )
        snap_obj = engine.get_terminal_snapshot(
            account_id=kwargs.get("account_id"),
            portfolio_id=kwargs.get("portfolio_id"),
            refresh=kwargs.get("refresh", True),
            persist=True,
            include_orders=True,
            include_history=True,
        )
        snapshot = snap_obj.to_dict() if hasattr(snap_obj, "to_dict") else snap_obj

        assistant = get_forex_ai_trade_assistant(db=self.db)
        risk = get_forex_institutional_risk_manager(db=self.db)
        monitor = get_forex_execution_monitor(db=self.db)

        ai_candidates = assistant.generate_candidates(limit=8, account_snapshot=snapshot.get("account"))

        production = {}
        try:
            from modules.forex.forex_phase12_production_services import get_forex_phase12_production_services
            prod = get_forex_phase12_production_services(db=self.db)
            production = {
                "broker_health": prod.broker_health(),
                "operations_health": prod.operations_health(),
                "institutional_risk": prod.institutional_risk(snapshot),
                "portfolio_attribution": prod.attribution(snapshot),
                "execution_analytics": prod.execution_analytics(),
                "ai_supervision": [
                    {
                        "candidate": c,
                        "review": prod.supervise_candidate(c, snapshot),
                    }
                    for c in ai_candidates[:5]
                ],
            }
        except Exception as exc:
            production = {"status": "ERROR", "error": str(exc)}

        return {
            "snapshot": snapshot,
            "ai_candidates": ai_candidates,
            "risk_assessment": risk.assess_snapshot(snapshot),
            "execution_blotter": monitor.blotter(limit=100),
            "production": production,
        }

    def quote_trade(self, **kwargs) -> Dict[str, Any]:
        from modules.forex.forex_institutional_trade_ticket import get_forex_institutional_trade_ticket
        return get_forex_institutional_trade_ticket(db=self.db).quote_ticket(**kwargs).to_dict()

    def submit_trade(self, **kwargs) -> Dict[str, Any]:
        from modules.forex.forex_institutional_trade_ticket import get_forex_institutional_trade_ticket
        return get_forex_institutional_trade_ticket(db=self.db).submit_ticket(**kwargs)

    def autonomous_cycle(self, **kwargs) -> Dict[str, Any]:
        from modules.forex.forex_autonomous_trading_engine import get_forex_autonomous_trading_engine
        return get_forex_autonomous_trading_engine(db=self.db).run_cycle(**kwargs)


_WORKSTATION = None


def get_forex_institutional_workstation(db: Optional[Any] = None) -> ForexInstitutionalWorkstation:
    global _WORKSTATION
    if _WORKSTATION is None or (db is not None and _WORKSTATION.db is None):
        _WORKSTATION = ForexInstitutionalWorkstation(db=db)
    return _WORKSTATION
