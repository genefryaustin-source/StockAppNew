from __future__ import annotations

import platform
import sys
from typing import Any, Dict, List

from modules.forex.forex_component_validator import ForexComponentValidator
from modules.forex.forex_health_monitor import ForexHealthMonitor
from modules.forex.forex_validation_engine import FAIL, PASS, WARN, ForexValidationEngine


class ForexDiagnosticEngine:
    """Produces a diagnostic bundle for Forex QA and troubleshooting."""

    def __init__(self, db: Any = None, user: Any = None) -> None:
        self.db = db
        self.user = user
        self.engine = ForexValidationEngine(db=db, user=user)

    def environment(self) -> Dict[str, Any]:
        return {
            "python": sys.version,
            "platform": platform.platform(),
            "executable": sys.executable,
        }

    def module_diagnostics(self) -> Dict[str, Any]:
        return ForexComponentValidator(db=self.db, user=self.user).run_all()

    def runtime_diagnostics(self) -> Dict[str, Any]:
        checks = [
            ("Health Monitor", lambda: ForexHealthMonitor(db=self.db, user=self.user).health_score()),
            ("Operations Snapshot", self.engine.check_operations_snapshot),
            ("Runtime Tick", lambda: self.engine.check_runtime_tick(max_jobs=1)),
            ("Optimizer", self.engine.check_optimizer),
        ]
        return self.engine.run_checks(checks, name="Forex Runtime Diagnostics").to_dict()

    def diagnose(self) -> Dict[str, Any]:
        module = self.module_diagnostics()
        runtime = self.runtime_diagnostics()
        health = ForexHealthMonitor(db=self.db, user=self.user).health_score()
        failed = module.get("failed", 0) + runtime.get("failed", 0)
        warned = module.get("warned", 0) + runtime.get("warned", 0)
        status = FAIL if failed else WARN if warned or health.get("status") != "healthy" else PASS
        return {
            "status": status,
            "environment": self.environment(),
            "health": health,
            "module_diagnostics": module,
            "runtime_diagnostics": runtime,
        }

    def quick_diagnose(self) -> Dict[str, Any]:
        health = ForexHealthMonitor(db=self.db, user=self.user).health_score()
        ops = self.engine.check_operations_snapshot().to_dict()
        return {"status": health.get("status"), "health": health, "operations": ops}
