
from __future__ import annotations
from typing import Dict, List
from modules.forex.ui.forex_enterprise_reports_summary import report_metrics
from modules.forex.ui.forex_ui_cards import render_metric_ribbon

def render_enterprise_reports_kpi_ribbon(rows: List[Dict]) -> None:
    m = report_metrics(rows)
    cards = [
        {"label": "Reports", "value": m.get("total_reports", 0), "caption": "Institutional packages", "progress": min(m.get("total_reports", 0) * 12, 100), "status": "ACTIVE", "icon": "📄"},
        {"label": "Generated", "value": m.get("generated", 0), "caption": "Ready outputs", "progress": min(m.get("generated", 0) * 16, 100), "status": "READY", "icon": "✅"},
        {"label": "Queued", "value": m.get("queued", 0), "caption": "Processing queue", "progress": min(m.get("queued", 0) * 25, 100), "status": "ACTIVE" if m.get("queued", 0) else "READY", "icon": "⏳"},
        {"label": "Pending", "value": m.get("pending", 0), "caption": "Awaiting inputs", "progress": min(m.get("pending", 0) * 25, 100), "status": "WATCH" if m.get("pending", 0) else "READY", "icon": "🟡"},
        {"label": "Failed", "value": m.get("failed", 0), "caption": "Report errors", "progress": max(0, 100 - m.get("failed", 0) * 25), "status": "WARNING" if m.get("failed", 0) else "READY", "icon": "⛔"},
        {"label": "Readiness", "value": f"{m.get('readiness', 0):.0f}%", "caption": "Average complete", "progress": m.get("readiness", 0), "status": "READY" if m.get("readiness", 0) >= 75 else "WATCH", "icon": "📊"},
        {"label": "Formats", "value": m.get("export_formats", 0), "caption": "PDF / DOCX / XLSX", "progress": min(m.get("export_formats", 0) * 25, 100), "status": "READY", "icon": "📦"},
        {"label": "Status", "value": "READY", "caption": "Report center", "progress": 100, "status": "READY", "icon": "🟢"},
    ]
    render_metric_ribbon(cards)
