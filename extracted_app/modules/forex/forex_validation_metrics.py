from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import csv


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_import(path: str, name: str):
    module = __import__(path, fromlist=[name])
    return getattr(module, name)


def _is_pass(value: Any) -> bool:
    if isinstance(value, dict):
        status = str(value.get("status", "")).lower()
        return bool(value.get("passed", False)) or status in {"pass", "passed", "success", "healthy", "clear", "completed"}
    return False


def _flatten_results(payload: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    def walk(obj: Any, prefix: str = "") -> None:
        if isinstance(obj, dict):
            name = obj.get("name") or obj.get("test") or obj.get("component") or prefix or "result"
            if "status" in obj or "passed" in obj:
                rows.append({
                    "name": str(name),
                    "status": str(obj.get("status", "pass" if obj.get("passed") else "unknown")),
                    "passed": _is_pass(obj),
                    "checked_at": obj.get("checked_at") or obj.get("completed_at") or _utc_now(),
                    "details": obj.get("details", obj),
                })
            for key, value in obj.items():
                if isinstance(value, (dict, list)):
                    walk(value, str(key))
        elif isinstance(obj, list):
            for item in obj:
                walk(item, prefix)

    walk(payload)
    return rows

class ForexValidationMetrics:
    """Computes aggregate metrics from validation, stress, resiliency, and diagnostic results."""

    def summarize(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        rows = _flatten_results(payload)
        total = len(rows)
        passed = sum(1 for row in rows if row.get("passed"))
        failed = total - passed
        score = round((passed / total) * 100, 2) if total else 0.0
        return {
            "status": "pass" if failed == 0 and total > 0 else "fail" if failed else "unknown",
            "score": score,
            "total_checks": total,
            "passed": passed,
            "failed": failed,
            "generated_at": _utc_now(),
            "rows": rows,
        }

    def component_breakdown(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        rows = _flatten_results(payload)
        buckets: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            component = str(row.get("name", "unknown")).split("_")[0] or "unknown"
            bucket = buckets.setdefault(component, {"component": component, "total": 0, "passed": 0, "failed": 0})
            bucket["total"] += 1
            if row.get("passed"):
                bucket["passed"] += 1
            else:
                bucket["failed"] += 1
        for bucket in buckets.values():
            bucket["score"] = round((bucket["passed"] / bucket["total"]) * 100, 2) if bucket["total"] else 0.0
            bucket["status"] = "pass" if bucket["failed"] == 0 else "fail"
        return list(buckets.values())

    def trend_point(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        summary = self.summarize(payload)
        return {
            "timestamp": _utc_now(),
            "score": summary["score"],
            "total_checks": summary["total_checks"],
            "passed": summary["passed"],
            "failed": summary["failed"],
            "status": summary["status"],
        }


def summarize_validation_metrics(payload: Dict[str, Any]) -> Dict[str, Any]:
    return ForexValidationMetrics().summarize(payload)
