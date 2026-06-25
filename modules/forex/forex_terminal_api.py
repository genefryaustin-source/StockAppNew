"""
modules/forex/forex_terminal_api.py

Cycle-safe terminal API.

No module-level imports from institutional terminal or trading desk. Those are
loaded lazily inside methods.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class ForexTerminalAPI:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def get_terminal_snapshot(self, **kwargs) -> Dict[str, Any]:
        try:
            from modules.forex.forex_institutional_terminal import get_forex_institutional_terminal
            terminal = get_forex_institutional_terminal(db=self.db)
            if hasattr(terminal, "snapshot"):
                return terminal.snapshot(**kwargs)
            return {"status": "READY", "component": type(terminal).__name__}
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    def refresh_terminal(self) -> Dict[str, Any]:
        try:
            from modules.forex.forex_service import get_forex_service
            service = get_forex_service(db=self.db)
            refresh = service.refresh_market_data()
        except Exception as exc:
            refresh = {"status": "WARNING", "error": str(exc)}
        snap = self.get_terminal_snapshot()
        return {"status": "REFRESHED", "refresh": refresh, "snapshot": snap}

    def submit_order(self, **kwargs):
        from modules.forex.forex_execution_center import get_forex_execution_center
        return get_forex_execution_center(db=self.db).submit_order(**kwargs)

    def cancel_order(self, broker_order_id):
        from modules.forex.forex_execution_center import get_forex_execution_center
        return get_forex_execution_center(db=self.db).cancel_order(broker_order_id)

    def execute_recommendation(self, recommendation, **kwargs):
        from modules.forex.forex_execution_center import get_forex_execution_center
        return get_forex_execution_center(db=self.db).execute_recommendation(recommendation, **kwargs)

    def run_autonomous_cycle(self, **kwargs):
        from modules.forex.forex_trading_desk import get_forex_trading_desk
        desk = get_forex_trading_desk(db=self.db)
        if hasattr(desk, "autonomous_cycle"):
            return desk.autonomous_cycle(**kwargs)
        return {"status": "UNAVAILABLE"}

    def emergency_stop(self):
        from modules.forex.forex_trading_desk import get_forex_trading_desk
        desk = get_forex_trading_desk(db=self.db)
        if hasattr(desk, "emergency_kill_switch"):
            return desk.emergency_kill_switch()
        return {"status": "UNAVAILABLE"}

    def provider_health(self):
        try:
            from modules.forex.forex_provider_health import get_forex_provider_health
            return get_forex_provider_health().summary()
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    def portfolio_summary(self, **kwargs):
        try:
            from modules.forex.forex_portfolio_manager import get_forex_portfolio_manager
            return get_forex_portfolio_manager(db=self.db).portfolio_summary(**kwargs)
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    def render(self):
        try:
            from modules.forex.forex_workspace import render_forex_workspace
            return render_forex_workspace(db=self.db)
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}


_API = None


def get_forex_terminal_api(db: Optional[Any] = None) -> ForexTerminalAPI:
    global _API
    if _API is None or (db is not None and _API.db is None):
        _API = ForexTerminalAPI(db=db)
    return _API
