"""
modules/forex/forex_trading_workspace.py

Phase 6 — Bloomberg-Class Live Trading Workspace.

This is the institutional workspace facade used by the terminal dashboard. It
aggregates live portfolio state, trade ticket analytics, AI candidates,
execution blotter, watchlist, order-book view, market depth, journal, and risk.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexTradingWorkspace:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def workspace_snapshot(self, **kwargs) -> Dict[str, Any]:
        from modules.forex.forex_institutional_workstation import get_forex_institutional_workstation
        from modules.forex.forex_watchlist_manager import get_forex_watchlist_manager
        from modules.forex.forex_order_book import get_forex_order_book
        from modules.forex.forex_market_depth import get_forex_market_depth
        from modules.forex.forex_trade_journal import get_forex_trade_journal
        from modules.forex.forex_execution_blotter import get_forex_execution_blotter
        from modules.forex.forex_ai_command_center import get_forex_ai_command_center
        from modules.forex.forex_economic_intelligence import get_forex_economic_intelligence
        from modules.forex.forex_microstructure_engine import get_forex_microstructure_engine

        pair = kwargs.get("pair") or "EUR/USD"

        workstation = get_forex_institutional_workstation(db=self.db)
        state = workstation.terminal_state(**kwargs)

        return {
            "status": "READY",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "pair": pair,
            "terminal": state,
            "watchlist": get_forex_watchlist_manager(db=self.db).get_watchlist(**kwargs),
            "order_book": get_forex_order_book(db=self.db).book(pair=pair, **kwargs),
            "market_depth": get_forex_market_depth(db=self.db).depth(pair=pair, **kwargs),
            "journal": get_forex_trade_journal(db=self.db).entries(**kwargs),
            "execution_blotter": get_forex_execution_blotter(db=self.db).blotter(**kwargs),
            "ai_command_center": get_forex_ai_command_center(db=self.db).briefing(**kwargs),
            "economic_intelligence": get_forex_economic_intelligence(db=self.db).dashboard(**kwargs),
            "microstructure": get_forex_microstructure_engine(db=self.db).dashboard(pair=pair, **kwargs),
        }

    def quote_trade(self, **kwargs) -> Dict[str, Any]:
        from modules.forex.forex_institutional_workstation import get_forex_institutional_workstation
        return get_forex_institutional_workstation(db=self.db).quote_trade(**kwargs)

    def submit_trade(self, **kwargs) -> Dict[str, Any]:
        from modules.forex.forex_institutional_workstation import get_forex_institutional_workstation
        return get_forex_institutional_workstation(db=self.db).submit_trade(**kwargs)

    def autonomous_cycle(self, **kwargs) -> Dict[str, Any]:
        from modules.forex.forex_autonomous_portfolio_manager import get_forex_autonomous_portfolio_manager
        return get_forex_autonomous_portfolio_manager(db=self.db).run_cycle(**kwargs)


_WORKSPACE = None


def get_forex_trading_workspace(db: Optional[Any] = None) -> ForexTradingWorkspace:
    global _WORKSPACE
    if _WORKSPACE is None or (db is not None and _WORKSPACE.db is None):
        _WORKSPACE = ForexTradingWorkspace(db=db)
    return _WORKSPACE
