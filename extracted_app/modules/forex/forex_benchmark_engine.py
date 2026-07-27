"""
modules/forex/forex_benchmark_engine.py

Phase 20E — Benchmark engine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexBenchmarkEngine:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def benchmark(self) -> Dict[str, Any]:
        return {
            "status": "READY",
            "benchmark": "Equal-weight G10 FX basket",
            "portfolio_return_pct": 0.0,
            "benchmark_return_pct": 0.0,
            "excess_return_pct": 0.0,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_ENGINE = None


def get_forex_benchmark_engine(db: Optional[Any] = None) -> ForexBenchmarkEngine:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexBenchmarkEngine(db=db)
    return _ENGINE
