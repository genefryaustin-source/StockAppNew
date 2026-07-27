from __future__ import annotations
import time
from typing import Any, Dict, List

try:
    from .forex_supervisor import ForexSupervisor
except Exception:
    from forex_supervisor import ForexSupervisor


class ForexContinuousRuntimeEngine:
    """Bounded continuous loop for local workers or Streamlit-triggered cycles."""

    def __init__(self, supervisor: ForexSupervisor | None = None) -> None:
        self.supervisor = supervisor or ForexSupervisor()

    def run_loop(self, cycles: int = 1, sleep_seconds: float = 1.0, max_jobs_per_cycle: int = 10) -> Dict[str, Any]:
        results: List[Dict[str, Any]] = []
        for _ in range(max(1, int(cycles))):
            results.append(self.supervisor.supervise_tick(max_jobs=max_jobs_per_cycle))
            if cycles > 1:
                time.sleep(max(0.0, float(sleep_seconds)))
        return {"cycles": len(results), "results": results}
