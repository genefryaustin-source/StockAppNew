"""
modules/forex/forex_autonomous_portfolio_manager.py

Autonomous portfolio manager for paper FX trades.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexAutonomousPortfolioManager:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def run_cycle(self, **kwargs) -> Dict[str, Any]:
        from modules.forex.forex_autonomous_trading_engine import get_forex_autonomous_trading_engine
        result = get_forex_autonomous_trading_engine(db=self.db).run_cycle(**kwargs)
        result["portfolio_manager"] = {
            "scale_in": "enabled_paper",
            "scale_out": "enabled_paper",
            "trail_stops": "planned",
            "auto_hedge": "planned",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        return result

    def manage_open_positions(self, **kwargs) -> Dict[str, Any]:
        from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine

        engine = get_forex_portfolio_engine(
            tenant_id=kwargs.get("tenant_id"),
            user_id=kwargs.get("user_id"),
            portfolio_id=kwargs.get("portfolio_id"),
            db=self.db,
        )
        snap = engine.get_terminal_snapshot(
            account_id=kwargs.get("account_id"),
            portfolio_id=kwargs.get("portfolio_id"),
            refresh=True,
            persist=True,
            include_orders=True,
            include_history=True,
        )
        snapshot = snap.to_dict() if hasattr(snap, "to_dict") else snap
        actions = []
        for pos in snapshot.get("positions", []):
            pnl = float(pos.get("unrealized_pnl") or pos.get("P/L") or 0)
            if pnl > 0:
                actions.append({"position": pos.get("id") or pos.get("Symbol"), "action": "monitor_winner"})
            elif pnl < 0:
                actions.append({"position": pos.get("id") or pos.get("Symbol"), "action": "risk_review"})
        return {"status": "READY", "actions": actions, "snapshot": snapshot}


_MANAGER = None


def get_forex_autonomous_portfolio_manager(db: Optional[Any] = None) -> ForexAutonomousPortfolioManager:
    global _MANAGER
    if _MANAGER is None or (db is not None and _MANAGER.db is None):
        _MANAGER = ForexAutonomousPortfolioManager(db=db)
    return _MANAGER
