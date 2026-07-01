"""
modules/forex/forex_autonomous_command_center.py

Phase 20G — Autonomous institutional command center.

Top-level orchestrator for autonomous research and paper-trading workflows.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexAutonomousCommandCenter:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def dashboard(self, snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        snapshot = snapshot or {}

        from modules.forex.forex_executive_command_center import get_forex_executive_command_center
        from modules.forex.forex_autonomous_strategy_orchestrator import get_forex_autonomous_strategy_orchestrator
        from modules.forex.forex_learning_engine import get_forex_learning_engine
        from modules.forex.forex_dynamic_allocation_engine import get_forex_dynamic_allocation_engine
        from modules.forex.forex_execution_supervisor import get_forex_execution_supervisor
        from modules.forex.forex_manager_dashboard import get_forex_manager_dashboard
        from modules.forex.forex_enterprise_operations_center_v2 import get_forex_enterprise_operations_center_v2

        return {
            "status": "READY",
            "mode": "paper_trading_autonomous_research",
            "live_execution_enabled": False,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "executive_decision_center": get_forex_executive_command_center(db=self.db).dashboard(snapshot=snapshot),
            "autonomous_strategies": get_forex_autonomous_strategy_orchestrator(db=self.db).orchestrate(snapshot=snapshot),
            "learning_engine": get_forex_learning_engine(db=self.db).dashboard(),
            "portfolio_manager": get_forex_dynamic_allocation_engine(db=self.db).dashboard(),
            "execution_intelligence": get_forex_execution_supervisor(db=self.db).dashboard(),
            "performance_analytics": get_forex_manager_dashboard(db=self.db).dashboard(),
            "enterprise_operations": get_forex_enterprise_operations_center_v2(db=self.db).dashboard(),
        }


_ENGINE = None


def get_forex_autonomous_command_center(db: Optional[Any] = None) -> ForexAutonomousCommandCenter:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexAutonomousCommandCenter(db=db)
    return _ENGINE
