"""
modules/forex/forex_terminal_api.py

Phase 4 API:
- terminal snapshot prefers ForexPortfolioEngine
- submit_order validates + executes through ForexTerminalExecutionService
- execution result returns updated snapshot for dashboard auto-refresh
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class ForexTerminalAPI:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def get_terminal_snapshot(self, **kwargs) -> Dict[str, Any]:
        try:
            from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine
            engine = get_forex_portfolio_engine(
                tenant_id=kwargs.get("tenant_id"),
                user_id=kwargs.get("user_id"),
                portfolio_id=kwargs.get("portfolio_id"),
                db=self.db,
            )
            snapshot = engine.get_terminal_snapshot(
                account_id=kwargs.get("account_id"),
                portfolio_id=kwargs.get("portfolio_id"),
                refresh=kwargs.get("refresh", True),
                persist=True,
                include_orders=True,
                include_history=True,
            )
            return snapshot.to_dict() if hasattr(snapshot, "to_dict") else snapshot
        except Exception as portfolio_exc:
            portfolio_error = str(portfolio_exc)

        try:
            from modules.forex.forex_institutional_terminal import get_forex_institutional_terminal
            terminal = get_forex_institutional_terminal(db=self.db)
            snap = terminal.snapshot(**kwargs) if hasattr(terminal, "snapshot") else {}
            if isinstance(snap, dict):
                snap.setdefault("portfolio_engine_error", portfolio_error)
            return snap if isinstance(snap, dict) else {"status": "READY", "payload": snap}
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc), "portfolio_engine_error": portfolio_error}

    def refresh_terminal(self) -> Dict[str, Any]:
        try:
            from modules.forex.forex_service import get_forex_service
            refresh = get_forex_service(db=self.db).refresh_market_data()
        except Exception as exc:
            refresh = {"status": "WARNING", "error": str(exc)}
        return {"status": "REFRESHED", "refresh": refresh, "snapshot": self.get_terminal_snapshot(refresh=True)}

    def validate_order(self, **kwargs):
        from modules.forex.forex_terminal_execution_service import get_forex_terminal_execution_service
        return get_forex_terminal_execution_service(db=self.db).validate_order(**kwargs)

    def submit_order(self, **kwargs):
        try:
            from modules.forex.forex_terminal_execution_service import get_forex_terminal_execution_service
            return get_forex_terminal_execution_service(db=self.db).submit_order(**kwargs)
        except Exception as exc:
            primary_error = str(exc)

        try:
            from modules.forex.forex_execution_center import get_forex_execution_center
            result = get_forex_execution_center(db=self.db).submit_order(**kwargs)
            if isinstance(result, dict):
                result.setdefault("terminal_execution_error", primary_error)
            return result
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc), "terminal_execution_error": primary_error}

    def cancel_order(self, broker_order_id):
        try:
            from modules.forex.forex_terminal_execution_service import get_forex_terminal_execution_service
            return get_forex_terminal_execution_service(db=self.db).cancel_order(broker_order_id)
        except Exception:
            from modules.forex.forex_execution_center import get_forex_execution_center
            return get_forex_execution_center(db=self.db).cancel_order(broker_order_id)

    def execute_recommendation(self, recommendation, **kwargs):
        payload = dict(recommendation or {})
        payload.update(kwargs)
        if "pair" not in payload and "symbol" in payload:
            payload["pair"] = payload["symbol"]
        if "side" not in payload:
            payload["side"] = payload.get("direction") or payload.get("recommendation") or "BUY"
        if "units" not in payload and "qty" not in payload and "lots" not in payload:
            payload["units"] = payload.get("suggested_units") or payload.get("suggested_qty") or 100000
        return self.submit_order(**payload)

    def provider_health(self):
        try:
            from modules.forex.forex_provider_health import get_forex_provider_health
            return get_forex_provider_health().summary()
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    def portfolio_summary(self, **kwargs):
        try:
            from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine
            engine = get_forex_portfolio_engine(
                tenant_id=kwargs.get("tenant_id"),
                user_id=kwargs.get("user_id"),
                portfolio_id=kwargs.get("portfolio_id"),
                db=self.db,
            )
            account = engine.get_or_create_account(portfolio_id=kwargs.get("portfolio_id"))
            snap = engine.get_snapshot(account_id=account.id, persist=True, refresh=kwargs.get("refresh", True))
            return snap.to_dict() if hasattr(snap, "to_dict") else snap
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    def run_autonomous_cycle(self, **kwargs):
        from modules.forex.forex_trading_desk import get_forex_trading_desk
        desk = get_forex_trading_desk(db=self.db)
        return desk.autonomous_cycle(**kwargs) if hasattr(desk, "autonomous_cycle") else {"status": "UNAVAILABLE"}

    def emergency_stop(self):
        from modules.forex.forex_trading_desk import get_forex_trading_desk
        desk = get_forex_trading_desk(db=self.db)
        return desk.emergency_kill_switch() if hasattr(desk, "emergency_kill_switch") else {"status": "UNAVAILABLE"}

    def render(self):
        try:
            from modules.forex.forex_workspace import render_forex_workspace
            return render_forex_workspace(
                db=self.db,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                portfolio_id=self.portfolio_id,
            )
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}


_API = None


def get_forex_terminal_api(db: Optional[Any] = None) -> ForexTerminalAPI:
    global _API
    if _API is None or (db is not None and _API.db is None):
        _API = ForexTerminalAPI(db=db)
    return _API
