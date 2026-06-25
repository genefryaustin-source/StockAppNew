"""
modules/forex/forex_institutional_terminal.py

Cycle-safe Institutional Forex terminal facade.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexInstitutionalTerminal:
    VERSION = "1.0.0"

    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def snapshot(self, **kwargs) -> Dict[str, Any]:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "terminal": "Forex Institutional Terminal",
            "version": self.VERSION,
            "status": "READY",
            "market_overview": self.market_overview(),
            "portfolio": self._safe_portfolio_summary(**kwargs),
            "provider_health": self._safe_provider_health(),
        }

    def render(self, *args: Any, **kwargs: Any):
        try:
            from modules.forex.forex_institutional_command_center import render_forex_institutional_command_center
            kwargs.setdefault("db", self.db)
            return render_forex_institutional_command_center(*args, **kwargs)
        except Exception as exc:
            try:
                import streamlit as st
                st.error(f"Institutional terminal failed: {exc}")
            except Exception:
                pass
            return {"status": "ERROR", "error": str(exc)}

    def dashboard(self):
        try:
            from modules.forex.forex_terminal_dashboard import get_forex_terminal_dashboard
            return get_forex_terminal_dashboard(db=self.db)
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    def market_overview(self) -> Dict[str, Any]:
        try:
            from modules.forex.forex_service import get_forex_service
            service = get_forex_service(db=self.db)
            return service.get_command_center()
        except Exception as exc:
            return {"status": "WARNING", "error": str(exc)}

    def trading_workspace(self):
        from modules.forex.forex_trading_desk import get_forex_trading_desk
        return get_forex_trading_desk(db=self.db)

    def portfolio_workspace(self):
        from modules.forex.forex_portfolio_manager import get_forex_portfolio_manager
        return get_forex_portfolio_manager(db=self.db)

    def institutional_workspace(self) -> Dict[str, Any]:
        return {
            "terminal": self.snapshot(),
            "trading_workspace": "ForexTradingDesk",
            "portfolio_workspace": "ForexPortfolioManager",
        }

    def ai_workspace(self):
        from modules.forex.forex_ai_assistant import get_forex_ai_assistant
        return get_forex_ai_assistant(db=self.db)

    def status(self) -> Dict[str, Any]:
        return {
            "terminal": "Forex Institutional Terminal",
            "version": self.VERSION,
            "status": "READY",
        }

    def _safe_portfolio_summary(self, **kwargs):
        try:
            from modules.forex.forex_portfolio_manager import get_forex_portfolio_manager
            return get_forex_portfolio_manager(db=self.db).portfolio_summary(**kwargs)
        except Exception as exc:
            return {"status": "WARNING", "error": str(exc)}

    def _safe_provider_health(self):
        try:
            from modules.forex.forex_provider_health import get_forex_provider_health
            return get_forex_provider_health().summary()
        except Exception as exc:
            return {"status": "WARNING", "error": str(exc)}


_INSTANCE = None


def get_forex_institutional_terminal(db: Optional[Any] = None) -> ForexInstitutionalTerminal:
    global _INSTANCE
    if _INSTANCE is None or (db is not None and _INSTANCE.db is None):
        _INSTANCE = ForexInstitutionalTerminal(db=db)
    return _INSTANCE
