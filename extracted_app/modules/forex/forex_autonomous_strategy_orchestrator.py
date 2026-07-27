"""
modules/forex/forex_autonomous_strategy_orchestrator.py

Phase 20A — Autonomous strategy orchestrator.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexAutonomousStrategyOrchestrator:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def orchestrate(self, snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        from modules.forex.forex_strategy_scheduler import get_forex_strategy_scheduler
        from modules.forex.forex_strategy_selector import get_forex_strategy_selector
        from modules.forex.forex_strategy_allocator import get_forex_strategy_allocator
        from modules.forex.forex_executive_command_center import get_forex_executive_command_center

        selector = get_forex_strategy_selector(db=self.db).select(snapshot=snapshot)
        selected = selector.get("selected_strategies", [])
        return {
            "status": "READY",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "scheduler": get_forex_strategy_scheduler(db=self.db).schedule(),
            "selector": selector,
            "allocator": get_forex_strategy_allocator(db=self.db).allocate(selected),
            "executive_decisions": get_forex_executive_command_center(db=self.db).dashboard(snapshot=snapshot or {}),
        }


_ENGINE = None


def get_forex_autonomous_strategy_orchestrator(db: Optional[Any] = None) -> ForexAutonomousStrategyOrchestrator:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexAutonomousStrategyOrchestrator(db=db)
    return _ENGINE
