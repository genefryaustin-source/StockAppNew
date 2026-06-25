from __future__ import annotations
from typing import Any, Dict, Optional

try:
    from .forex_common import ForexStateStore
    from .forex_execution_queue import ForexExecutionQueue
    from .forex_resource_governor import ForexResourceGovernor
except Exception:
    from forex_common import ForexStateStore
    from forex_execution_queue import ForexExecutionQueue
    from forex_resource_governor import ForexResourceGovernor


class ForexSelfDiagnosticEngine:
    """Runs health checks across the Forex operations stack."""

    def __init__(self, store: Optional[ForexStateStore] = None) -> None:
        self.store = store or ForexStateStore()
        self.queue = ForexExecutionQueue(self.store)
        self.governor = ForexResourceGovernor(self.store)

    def run_diagnostics(self) -> Dict[str, Any]:
        checks = []
        try:
            depth = self.queue.queue_depth()
            checks.append({"name": "queue_depth", "status": "pass", "details": depth})
        except Exception as exc:
            checks.append({"name": "queue_depth", "status": "fail", "details": str(exc)})
        try:
            limits = self.governor.evaluate_limits()
            status = "pass" if limits["max_concurrent_jobs"] >= 2 else "warn"
            checks.append({"name": "resource_governor", "status": status, "details": limits})
        except Exception as exc:
            checks.append({"name": "resource_governor", "status": "fail", "details": str(exc)})
        try:
            self.store.set_metric("diagnostic_probe", 1.0, {"probe": "ok"})
            checks.append({"name": "state_store", "status": "pass", "details": {"db_path": self.store.db_path}})
        except Exception as exc:
            checks.append({"name": "state_store", "status": "fail", "details": str(exc)})
        failed = sum(1 for c in checks if c["status"] == "fail")
        warned = sum(1 for c in checks if c["status"] == "warn")
        health_score = max(0, 100 - failed * 35 - warned * 10)
        self.store.set_metric("diagnostic_health_score", health_score, {"checks": checks})
        return {"health_score": health_score, "checks": checks, "status": "healthy" if health_score >= 80 else "degraded"}
