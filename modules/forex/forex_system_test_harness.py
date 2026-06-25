from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from modules.forex.forex_component_validator import ForexComponentValidator
from modules.forex.forex_diagnostic_engine import ForexDiagnosticEngine
from modules.forex.forex_health_monitor import ForexHealthMonitor
from modules.forex.forex_integration_test_suite import ForexIntegrationTestSuite
from modules.forex.forex_self_test_engine import ForexSelfTestEngine
from modules.forex.forex_validation_suite import ForexValidationSuite


class ForexSystemTestHarness:
    """Programmatic test harness for local, Streamlit, and pre-deployment validation runs."""

    def __init__(self, db: Any = None, user: Any = None, output_dir: Optional[str] = None) -> None:
        self.db = db
        self.user = user
        self.output_dir = Path(output_dir or "forex_validation_reports")

    def run_smoke(self) -> Dict[str, Any]:
        return ForexSelfTestEngine(db=self.db, user=self.user).run_smoke_test()

    def run_components(self) -> Dict[str, Any]:
        return ForexComponentValidator(db=self.db, user=self.user).run_all()

    def run_integration(self) -> Dict[str, Any]:
        return ForexIntegrationTestSuite(db=self.db, user=self.user).run_all()

    def run_health(self) -> Dict[str, Any]:
        return ForexHealthMonitor(db=self.db, user=self.user).health_score()

    def run_diagnostics(self) -> Dict[str, Any]:
        return ForexDiagnosticEngine(db=self.db, user=self.user).diagnose()

    def run_full(self) -> Dict[str, Any]:
        return ForexValidationSuite(db=self.db, user=self.user).run_full_validation()

    def run_release_gate(self) -> Dict[str, Any]:
        result = ForexSelfTestEngine(db=self.db, user=self.user).certify()
        result["release_gate_passed"] = bool(result.get("certified"))
        return result

    def save_report(self, report: Dict[str, Any], filename: Optional[str] = None) -> str:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self.output_dir / (filename or f"forex_validation_report_{stamp}.json")
        path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        return str(path)

    def run_and_save_full(self) -> Dict[str, Any]:
        report = self.run_full()
        report["report_path"] = self.save_report(report)
        return report


def run_forex_system_tests(db: Any = None, user: Any = None) -> Dict[str, Any]:
    return ForexSystemTestHarness(db=db, user=user).run_full()


if __name__ == "__main__":
    result = ForexSystemTestHarness().run_and_save_full()
    print(json.dumps(result, indent=2, default=str))
