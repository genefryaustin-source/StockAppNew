from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_import(path: str, name: str):
    module = __import__(path, fromlist=[name])
    return getattr(module, name)


def _status_ok(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    status = str(value.get("status", "")).lower()
    return bool(value.get("passed", False)) or status in {
        "pass", "passed", "success", "healthy", "clear", "completed",
        "certified", "ready", "approved", "online", "optimized"
    }

class ForexValidationSLOEngine:
    """Service-level objective tracker for Forex validation reliability and quality."""

    DEFAULT_SLO = {
        "target_success_rate": 99.0,
        "target_certification_rate": 95.0,
        "target_average_score": 95.0,
        "target_failure_rate_max": 1.0,
    }

    def __init__(self, slo: Optional[Dict[str, Any]] = None):
        self.slo = dict(self.DEFAULT_SLO)
        if slo:
            self.slo.update(slo)

    def calculate(self, runs: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        if runs is None:
            Persistence = _safe_import(
                "modules.forex.forex_validation_persistence",
                "ForexValidationPersistence",
            )
            runs = Persistence().list_runs(limit=500)

        total = len(runs)
        if total == 0:
            return {
                "status": "empty",
                "slo": self.slo,
                "total_runs": 0,
                "checked_at": _utc_now(),
            }

        successful = sum(1 for run in runs if _status_ok(run))
        scores: List[float] = []
        certified = 0

        for run in runs:
            result = run.get("result", run)
            scorecard = result.get("scorecard", {}) if isinstance(result, dict) else {}
            score = scorecard.get("score")
            if score is not None:
                try:
                    scores.append(float(score))
                except Exception:
                    pass
            if scorecard.get("certified") or str(scorecard.get("status", "")).lower() == "certified":
                certified += 1

        success_rate = round((successful / total) * 100, 2)
        certification_rate = round((certified / total) * 100, 2)
        failure_rate = round(((total - successful) / total) * 100, 2)
        average_score = round(sum(scores) / len(scores), 2) if scores else 0.0

        checks = [
            {
                "name": "target_success_rate",
                "target": self.slo["target_success_rate"],
                "actual": success_rate,
                "passed": success_rate >= float(self.slo["target_success_rate"]),
            },
            {
                "name": "target_certification_rate",
                "target": self.slo["target_certification_rate"],
                "actual": certification_rate,
                "passed": certification_rate >= float(self.slo["target_certification_rate"]),
            },
            {
                "name": "target_average_score",
                "target": self.slo["target_average_score"],
                "actual": average_score,
                "passed": average_score >= float(self.slo["target_average_score"]),
            },
            {
                "name": "target_failure_rate_max",
                "target": self.slo["target_failure_rate_max"],
                "actual": failure_rate,
                "passed": failure_rate <= float(self.slo["target_failure_rate_max"]),
            },
        ]

        violations = [check for check in checks if not check["passed"]]

        return {
            "status": "pass" if not violations else "fail",
            "slo": self.slo,
            "total_runs": total,
            "successful_runs": successful,
            "failed_runs": total - successful,
            "success_rate": success_rate,
            "certification_rate": certification_rate,
            "failure_rate": failure_rate,
            "average_score": average_score,
            "checks": checks,
            "violations": violations,
            "checked_at": _utc_now(),
        }

    def error_budget(self, runs: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        result = self.calculate(runs=runs)
        total = int(result.get("total_runs", 0) or 0)
        if total == 0:
            return {
                "status": "empty",
                "error_budget_remaining": 0,
                "checked_at": _utc_now(),
            }

        max_failure_rate = float(self.slo["target_failure_rate_max"])
        allowed_failures = int((max_failure_rate / 100.0) * total)
        actual_failures = int(result.get("failed_runs", 0) or 0)

        return {
            "status": "healthy" if actual_failures <= allowed_failures else "exhausted",
            "allowed_failures": allowed_failures,
            "actual_failures": actual_failures,
            "error_budget_remaining": max(0, allowed_failures - actual_failures),
            "checked_at": _utc_now(),
        }


def calculate_forex_validation_slo() -> Dict[str, Any]:
    return ForexValidationSLOEngine().calculate()
