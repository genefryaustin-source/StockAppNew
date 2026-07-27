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

class ForexValidationReporter:
    """Generates JSON, Markdown, HTML, and CSV validation reports."""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = Path(output_dir or "reports/forex")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def build_report(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        Scorecard = _safe_import("modules.forex.forex_validation_scorecard", "ForexValidationScorecard")
        Metrics = _safe_import("modules.forex.forex_validation_metrics", "ForexValidationMetrics")
        scorecard = Scorecard().build(payload)
        metrics = Metrics().summarize(payload)
        return {
            "report_type": "forex_validation_report",
            "generated_at": _utc_now(),
            "scorecard": scorecard,
            "metrics": metrics,
            "raw": payload,
        }

    def to_json(self, payload: Dict[str, Any], filename: Optional[str] = None) -> str:
        report = self.build_report(payload)
        path = self.output_dir / (filename or f"forex_validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        return str(path)

    def to_markdown(self, payload: Dict[str, Any], filename: Optional[str] = None) -> str:
        Scorecard = _safe_import("modules.forex.forex_validation_scorecard", "ForexValidationScorecard")
        markdown = Scorecard().markdown(payload)
        path = self.output_dir / (filename or f"forex_validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
        path.write_text(markdown, encoding="utf-8")
        return str(path)

    def to_html(self, payload: Dict[str, Any], filename: Optional[str] = None) -> str:
        report = self.build_report(payload)
        card = report["scorecard"]
        rows = report["metrics"].get("rows", [])
        row_html = "\\n".join(
            f"<tr><td>{r.get('name')}</td><td>{r.get('status')}</td><td>{r.get('checked_at')}</td></tr>"
            for r in rows
        )
        html = f"""<!doctype html>
<html>
<head><meta charset="utf-8"><title>Forex Validation Report</title></head>
<body>
<h1>Forex Validation Report</h1>
<p>Generated: {report['generated_at']}</p>
<h2>Scorecard</h2>
<ul>
<li>Status: {card['status']}</li>
<li>Score: {card['score']}%</li>
<li>Grade: {card['grade']}</li>
<li>Passed: {card['passed']}</li>
<li>Failed: {card['failed']}</li>
</ul>
<h2>Checks</h2>
<table border="1" cellspacing="0" cellpadding="6">
<tr><th>Name</th><th>Status</th><th>Checked At</th></tr>
{row_html}
</table>
</body>
</html>"""
        path = self.output_dir / (filename or f"forex_validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
        path.write_text(html, encoding="utf-8")
        return str(path)

    def to_csv(self, payload: Dict[str, Any], filename: Optional[str] = None) -> str:
        report = self.build_report(payload)
        path = self.output_dir / (filename or f"forex_validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        rows = report["metrics"].get("rows", [])
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["name", "status", "passed", "checked_at"])
            writer.writeheader()
            for row in rows:
                writer.writerow({k: row.get(k) for k in ["name", "status", "passed", "checked_at"]})
        return str(path)

    def export_all(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "exported",
            "json": self.to_json(payload),
            "markdown": self.to_markdown(payload),
            "html": self.to_html(payload),
            "csv": self.to_csv(payload),
            "exported_at": _utc_now(),
        }


def generate_forex_validation_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    return ForexValidationReporter().export_all(payload)
