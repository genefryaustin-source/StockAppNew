"""
modules/forex/forex_phase12_production_services.py

Phase 12 production service facade.

Provides safe access to Phase 11 production services:
- broker router / registry
- institutional risk engine
- portfolio attribution
- execution analytics
- AI trade supervisor
- operations health monitor

All live brokers remain safety-locked unless their adapter config explicitly
sets enabled=True and live_enabled=True.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class ForexPhase12ProductionServices:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def broker_health(self) -> Dict[str, Any]:
        try:
            from modules.forex.forex_broker_router import get_forex_broker_router
            router = get_forex_broker_router(db=self.db)
            return {"status": "READY", "brokers": router.health()}
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc), "brokers": []}

    def operations_health(self) -> Dict[str, Any]:
        try:
            from modules.forex.forex_operations_health_monitor import get_forex_operations_health_monitor
            return get_forex_operations_health_monitor(db=self.db).snapshot()
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    def institutional_risk(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from modules.forex.forex_institutional_risk_engine import get_forex_institutional_risk_engine
            return get_forex_institutional_risk_engine(db=self.db).analyze(snapshot or {})
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    def attribution(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from modules.forex.forex_portfolio_attribution import get_forex_portfolio_attribution
            return get_forex_portfolio_attribution(db=self.db).attribute(snapshot or {})
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    def execution_analytics(self, orders=None) -> Dict[str, Any]:
        try:
            from modules.forex.forex_execution_analytics import get_forex_execution_analytics
            return get_forex_execution_analytics(db=self.db).analyze(orders=orders)
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    def supervise_candidate(self, candidate: Dict[str, Any], snapshot: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from modules.forex.forex_ai_trade_supervisor import get_forex_ai_trade_supervisor
            return get_forex_ai_trade_supervisor(db=self.db).review_trade(candidate or {}, snapshot or {})
        except Exception as exc:
            return {"approved": False, "quality_score": 0, "errors": [str(exc)], "warnings": []}

    def paper_broker_route_test(self, **kwargs) -> Dict[str, Any]:
        try:
            from modules.forex.forex_broker_router import get_forex_broker_router
            router = get_forex_broker_router(db=self.db, default_broker="paper")
            return router.route_order(
                broker="paper",
                pair=kwargs.get("pair", "EUR/USD"),
                side=kwargs.get("side", "BUY"),
                lots=kwargs.get("lots", 0.01),
                order_type=kwargs.get("order_type", "MARKET"),
                account_id=kwargs.get("account_id"),
                portfolio_id=kwargs.get("portfolio_id"),
                tenant_id=kwargs.get("tenant_id"),
                user_id=kwargs.get("user_id"),
            )
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}


_SERVICES = None


def get_forex_phase12_production_services(db: Optional[Any] = None) -> ForexPhase12ProductionServices:
    global _SERVICES
    if _SERVICES is None or (db is not None and _SERVICES.db is None):
        _SERVICES = ForexPhase12ProductionServices(db=db)
    return _SERVICES
