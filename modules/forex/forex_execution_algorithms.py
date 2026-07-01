"""
modules/forex/forex_execution_algorithms.py

Phase 14C — Institutional execution algorithm facade.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexExecutionAlgorithms:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def plan(self, *, pair: str, side: str, units: float, algo: str = "TWAP", slices: int = 5) -> Dict[str, Any]:
        algo = str(algo or "TWAP").upper()
        child_units = units / max(slices, 1)
        schedule = [
            {
                "slice": i + 1,
                "pair": pair,
                "side": side,
                "units": round(child_units, 2),
                "algo": algo,
                "status": "planned",
            }
            for i in range(slices)
        ]
        return {
            "status": "READY",
            "algo": algo,
            "pair": pair,
            "side": side,
            "parent_units": units,
            "slices": slices,
            "schedule": schedule,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_ALGOS = None


def get_forex_execution_algorithms(db: Optional[Any] = None) -> ForexExecutionAlgorithms:
    global _ALGOS
    if _ALGOS is None or (db is not None and _ALGOS.db is None):
        _ALGOS = ForexExecutionAlgorithms(db=db)
    return _ALGOS
