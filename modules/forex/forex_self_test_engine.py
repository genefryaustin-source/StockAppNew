from __future__ import annotations

from typing import Any, Dict

from modules.forex.forex_component_validator import ForexComponentValidator
from modules.forex.forex_diagnostic_engine import ForexDiagnosticEngine
from modules.forex.forex_health_monitor import ForexHealthMonitor
from modules.forex.forex_integration_test_suite import ForexIntegrationTestSuite
from modules.forex.forex_validation_engine import FAIL, PASS, WARN, ForexValidationEngine


class ForexSelfTestEngine:
    """One-call self-test entry point used by validation dashboards and release checks."""

    def __init__(self, db: Any = None, user: Any = None) -> None:
        self.db = db
        self.user = user

    def run_smoke_test(self) -> Dict[str, Any]:
        engine = ForexValidationEngine(db=self.db, user=self.user)
        return engine.run_core_validation()

    def run_component_self_test(self) -> Dict[str, Any]:
        return ForexComponentValidator(db=self.db, user=self.user).run_all()

    def run_runtime_self_test(self) -> Dict[str, Any]:
        return ForexIntegrationTestSuite(db=self.db, user=self.user).run_schedule_runtime_flow(max_jobs=5)

    def run_full_self_test(self) -> Dict[str, Any]:
        smoke = self.run_smoke_test()
        components = self.run_component_self_test()
        integration = ForexIntegrationTestSuite(db=self.db, user=self.user).run_all()
        diagnostics = ForexDiagnosticEngine(db=self.db, user=self.user).quick_diagnose()
        health = ForexHealthMonitor(db=self.db, user=self.user).health_score()
        failed = smoke.get("failed", 0) + components.get("failed", 0) + integration.get("failed", 0)
        warned = smoke.get("warned", 0) + components.get("warned", 0) + integration.get("warned", 0)
        status = FAIL if failed else WARN if warned or health.get("status") != "healthy" else PASS
        return {
            "status": status,
            "smoke_test": smoke,
            "component_self_test": components,
            "integration_test": integration,
            "diagnostics": diagnostics,
            "health": health,
        }

    def certify(self) -> Dict[str, Any]:
        result = self.run_full_self_test()
        result["certified"] = result.get("status") == PASS
        result["certification_label"] = "FOREX_SYSTEM_CERTIFIED" if result["certified"] else "FOREX_SYSTEM_NOT_CERTIFIED"
        return result
