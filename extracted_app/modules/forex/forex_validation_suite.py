from __future__ import annotations

from typing import Any, Dict

from modules.forex.forex_component_validator import ForexComponentValidator
from modules.forex.forex_diagnostic_engine import ForexDiagnosticEngine
from modules.forex.forex_health_monitor import ForexHealthMonitor
from modules.forex.forex_integration_test_suite import ForexIntegrationTestSuite
from modules.forex.forex_self_test_engine import ForexSelfTestEngine
from modules.forex.forex_validation_engine import FAIL, PASS, WARN, ForexValidationEngine


class ForexValidationSuite:
    """Top-level Sprint 1 validation suite."""

    def __init__(self, db: Any = None, user: Any = None) -> None:
        self.db = db
        self.user = user
        self.engine = ForexValidationEngine(db=db, user=user)

    def run_import_validation(self) -> Dict[str, Any]:
        checks = [
            ("Validation Engine", lambda: self.engine.check_import("modules.forex.forex_validation_engine", "ForexValidationEngine")),
            ("Validation Suite", lambda: self.engine.check_import("modules.forex.forex_validation_suite", "ForexValidationSuite")),
            ("System Test Harness", lambda: self.engine.check_import("modules.forex.forex_system_test_harness", "ForexSystemTestHarness")),
            ("Integration Test Suite", lambda: self.engine.check_import("modules.forex.forex_integration_test_suite", "ForexIntegrationTestSuite")),
            ("Component Validator", lambda: self.engine.check_import("modules.forex.forex_component_validator", "ForexComponentValidator")),
            ("Health Monitor", lambda: self.engine.check_import("modules.forex.forex_health_monitor", "ForexHealthMonitor")),
            ("Diagnostic Engine", lambda: self.engine.check_import("modules.forex.forex_diagnostic_engine", "ForexDiagnosticEngine")),
            ("Self Test Engine", lambda: self.engine.check_import("modules.forex.forex_self_test_engine", "ForexSelfTestEngine")),
        ]
        return self.engine.run_checks(checks, name="Forex Sprint 1 Import Validation").to_dict()

    def run_component_validation(self) -> Dict[str, Any]:
        return ForexComponentValidator(db=self.db, user=self.user).run_all()

    def run_health_validation(self) -> Dict[str, Any]:
        health = ForexHealthMonitor(db=self.db, user=self.user).health_score()
        status = PASS if health.get("status") == "healthy" else WARN if health.get("status") == "degraded" else FAIL
        return {"status": status, "message": "Health validation completed.", "health": health}

    def run_diagnostics(self) -> Dict[str, Any]:
        return ForexDiagnosticEngine(db=self.db, user=self.user).diagnose()

    def run_integration_validation(self) -> Dict[str, Any]:
        return ForexIntegrationTestSuite(db=self.db, user=self.user).run_all()

    def run_smoke_validation(self) -> Dict[str, Any]:
        return ForexSelfTestEngine(db=self.db, user=self.user).run_smoke_test()

    def run_full_validation(self) -> Dict[str, Any]:
        checks = [
            ("Sprint 1 Imports", self.run_import_validation),
            ("Core Smoke Validation", self.run_smoke_validation),
            ("Component Validation", self.run_component_validation),
            ("Health Validation", self.run_health_validation),
            ("Integration Validation", self.run_integration_validation),
            ("Diagnostics", self.run_diagnostics),
        ]
        report = self.engine.run_checks(checks, name="Forex Sprint 1 Full Validation").to_dict()
        report["certified"] = report.get("failed", 0) == 0
        return report

    def run_all(self) -> Dict[str, Any]:
        return self.run_full_validation()
