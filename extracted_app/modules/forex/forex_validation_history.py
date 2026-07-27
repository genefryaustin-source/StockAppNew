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

class ForexValidationHistory:
    """File-backed validation history store for local/dev and Streamlit deployments."""

    def __init__(self, history_path: Optional[str] = None):
        self.history_path = Path(history_path or "data/forex_validation_history.jsonl")

    def append(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        Metrics = _safe_import("modules.forex.forex_validation_metrics", "ForexValidationMetrics")
        point = Metrics().trend_point(payload)
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with self.history_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(point, default=str) + "\\n")
        return {"status": "saved", "path": str(self.history_path), "point": point, "saved_at": _utc_now()}

    def load(self, limit: int = 100) -> List[Dict[str, Any]]:
        if not self.history_path.exists():
            return []
        rows: List[Dict[str, Any]] = []
        with self.history_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        continue
        return rows[-int(limit):]

    def latest(self) -> Dict[str, Any]:
        rows = self.load(limit=1)
        return rows[0] if rows else {"status": "empty", "timestamp": _utc_now()}

    def clear(self) -> Dict[str, Any]:
        if self.history_path.exists():
            self.history_path.unlink()
        return {"status": "cleared", "path": str(self.history_path), "cleared_at": _utc_now()}


def append_forex_validation_history(payload: Dict[str, Any]) -> Dict[str, Any]:
    return ForexValidationHistory().append(payload)
