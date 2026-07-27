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

class ForexValidationScorecard:
    """Builds a concise validation scorecard with grade and certification status."""

    def grade(self, score: float) -> str:
        if score >= 98:
            return "A+"
        if score >= 95:
            return "A"
        if score >= 90:
            return "B"
        if score >= 80:
            return "C"
        if score >= 70:
            return "D"
        return "F"

    def build(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        Metrics = _safe_import("modules.forex.forex_validation_metrics", "ForexValidationMetrics")
        metrics = Metrics().summarize(payload)
        breakdown = Metrics().component_breakdown(payload)
        score = float(metrics.get("score", 0.0))
        failed = int(metrics.get("failed", 0) or 0)
        certified = failed == 0 and score >= 95.0
        return {
            "status": "certified" if certified else "not_certified",
            "certified": certified,
            "score": score,
            "grade": self.grade(score),
            "total_checks": metrics.get("total_checks", 0),
            "passed": metrics.get("passed", 0),
            "failed": failed,
            "component_breakdown": breakdown,
            "generated_at": _utc_now(),
        }

    def markdown(self, payload: Dict[str, Any]) -> str:
        card = self.build(payload)
        lines = [
            "# Forex Validation Scorecard",
            "",
            f"Generated: {card['generated_at']}",
            f"Status: {card['status']}",
            f"Score: {card['score']}%",
            f"Grade: {card['grade']}",
            f"Passed: {card['passed']}",
            f"Failed: {card['failed']}",
            "",
            "## Component Breakdown",
        ]
        for item in card["component_breakdown"]:
            lines.append(f"- {item['component']}: {item['status']} ({item['score']}%, {item['passed']}/{item['total']})")
        return "\\n".join(lines)


def build_forex_validation_scorecard(payload: Dict[str, Any]) -> Dict[str, Any]:
    return ForexValidationScorecard().build(payload)
