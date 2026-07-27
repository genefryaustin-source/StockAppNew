from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_import(path: str, name: str):
    module = __import__(path, fromlist=[name])
    return getattr(module, name)


def _is_success(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    status = str(payload.get("status", "")).lower()
    return bool(payload.get("passed", False)) or status in {
        "pass", "passed", "success", "healthy", "clear", "completed", "certified", "exported", "saved"
    }


def _run_callable(path: str, class_name: str, method_name: str = "run_all", **kwargs) -> Dict[str, Any]:
    try:
        cls = _safe_import(path, class_name)
        instance = cls()
        method = getattr(instance, method_name)
        try:
            result = method(**kwargs)
        except TypeError:
            result = method()
        return result if isinstance(result, dict) else {"status": "completed", "result": result, "completed_at": _utc_now()}
    except Exception as exc:
        return {
            "status": "unavailable",
            "passed": False,
            "module": path,
            "class": class_name,
            "method": method_name,
            "error": str(exc),
            "checked_at": _utc_now(),
        }

class ForexValidationCenter:
    """Unified orchestration layer for Forex validation, QA, stress, resiliency, reporting, and history."""

    def run_component_validation(self) -> Dict[str, Any]:
        return _run_callable(
            "modules.forex.forex_component_validator",
            "ForexComponentValidator",
            "run_all",
        )

    def run_validation_suite(self) -> Dict[str, Any]:
        return _run_callable(
            "modules.forex.forex_validation_suite",
            "ForexValidationSuite",
            "run_all",
        )

    def run_system_tests(self) -> Dict[str, Any]:
        return _run_callable(
            "modules.forex.forex_system_test_harness",
            "ForexSystemTestHarness",
            "run_all",
        )

    def run_integration_tests(self) -> Dict[str, Any]:
        return _run_callable(
            "modules.forex.forex_integration_test_suite",
            "ForexIntegrationTestSuite",
            "run_all",
        )

    def run_diagnostics(self) -> Dict[str, Any]:
        return _run_callable(
            "modules.forex.forex_diagnostic_engine",
            "ForexDiagnosticEngine",
            "run_all",
        )

    def run_health_monitor(self) -> Dict[str, Any]:
        return _run_callable(
            "modules.forex.forex_health_monitor",
            "ForexHealthMonitor",
            "run_all",
        )

    def run_self_tests(self) -> Dict[str, Any]:
        return _run_callable(
            "modules.forex.forex_self_test_engine",
            "ForexSelfTestEngine",
            "run_all",
        )

    def run_stress_test(self, jobs: int = 100) -> Dict[str, Any]:
        result = _run_callable(
            "modules.forex.forex_stress_framework",
            "ForexStressFramework",
            "run_stress_test",
            jobs=jobs,
        )
        if result.get("status") == "unavailable":
            result = _run_callable(
                "modules.forex.forex_scalability_tester",
                "ForexScalabilityTester",
                "run",
                jobs=jobs,
            )
        return result

    def run_benchmarks(self) -> Dict[str, Any]:
        return _run_callable(
            "modules.forex.forex_benchmark_suite",
            "ForexBenchmarkSuite",
            "run_all",
        )

    def run_performance_profile(self) -> Dict[str, Any]:
        return _run_callable(
            "modules.forex.forex_performance_profiler",
            "ForexPerformanceProfiler",
            "run_all",
        )

    def run_resiliency_tests(self) -> Dict[str, Any]:
        return _run_callable(
            "modules.forex.forex_resiliency_tester",
            "ForexResiliencyTester",
            "run_all",
        )

    def run_self_healing_validation(self) -> Dict[str, Any]:
        return _run_callable(
            "modules.forex.forex_self_healing_validator",
            "ForexSelfHealingValidator",
            "run_all",
        )

    def run_recovery_validation(self) -> Dict[str, Any]:
        return _run_callable(
            "modules.forex.forex_recovery_validator",
            "ForexRecoveryValidator",
            "run_all",
        )

    def run_watchdog(self) -> Dict[str, Any]:
        return _run_callable(
            "modules.forex.forex_runtime_watchdog",
            "ForexRuntimeWatchdog",
            "check_runtime_stall",
        )

    def run_anomaly_detection(self) -> Dict[str, Any]:
        return _run_callable(
            "modules.forex.forex_anomaly_detector",
            "ForexAnomalyDetector",
            "detect_snapshot_anomalies",
        )

    def run_full_validation(self, include_stress: bool = False, stress_jobs: int = 100) -> Dict[str, Any]:
        started = _utc_now()
        suites: Dict[str, Any] = {
            "component_validation": self.run_component_validation(),
            "validation_suite": self.run_validation_suite(),
            "system_tests": self.run_system_tests(),
            "integration_tests": self.run_integration_tests(),
            "diagnostics": self.run_diagnostics(),
            "health_monitor": self.run_health_monitor(),
            "self_tests": self.run_self_tests(),
            "resiliency": self.run_resiliency_tests(),
            "self_healing": self.run_self_healing_validation(),
            "recovery": self.run_recovery_validation(),
            "watchdog": self.run_watchdog(),
            "anomaly_detection": self.run_anomaly_detection(),
        }
        if include_stress:
            suites["stress_test"] = self.run_stress_test(jobs=stress_jobs)
            suites["benchmarks"] = self.run_benchmarks()
            suites["performance_profile"] = self.run_performance_profile()

        passed = sum(1 for value in suites.values() if _is_success(value))
        failed = len(suites) - passed

        payload = {
            "status": "pass" if failed == 0 else "fail",
            "passed": passed,
            "failed": failed,
            "suite_count": len(suites),
            "started_at": started,
            "completed_at": _utc_now(),
            "suites": suites,
        }

        try:
            Scorecard = _safe_import("modules.forex.forex_validation_scorecard", "ForexValidationScorecard")
            payload["scorecard"] = Scorecard().build(payload)
        except Exception as exc:
            payload["scorecard_error"] = str(exc)

        return payload

    def generate_reports(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = payload or self.run_full_validation()
        Reporter = _safe_import("modules.forex.forex_validation_reporter", "ForexValidationReporter")
        return Reporter().export_all(payload)

    def save_history(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = payload or self.run_full_validation()
        History = _safe_import("modules.forex.forex_validation_history", "ForexValidationHistory")
        return History().append(payload)

    def latest_history(self) -> Dict[str, Any]:
        History = _safe_import("modules.forex.forex_validation_history", "ForexValidationHistory")
        return History().latest()

    def status(self) -> Dict[str, Any]:
        health = self.run_health_monitor()
        watchdog = self.run_watchdog()
        anomalies = self.run_anomaly_detection()
        return {
            "status": "healthy" if all(_is_success(x) for x in [health, watchdog, anomalies]) else "degraded",
            "health": health,
            "watchdog": watchdog,
            "anomalies": anomalies,
            "checked_at": _utc_now(),
        }


def run_forex_validation_center(include_stress: bool = False, stress_jobs: int = 100) -> Dict[str, Any]:
    return ForexValidationCenter().run_full_validation(
        include_stress=include_stress,
        stress_jobs=stress_jobs,
    )
