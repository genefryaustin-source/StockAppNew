
from __future__ import annotations
from typing import Dict, List
from modules.forex.ui.forex_signal_validation_summary import validation_metrics
from modules.forex.ui.forex_ui_cards import render_metric_ribbon

def render_signal_validation_kpi_ribbon(rows: List[Dict]) -> None:
    m = validation_metrics(rows)
    cards = [
        {"label": "Signals", "value": m.get("total", 0), "caption": "Reviewed candidates", "progress": min(m.get("total", 0) * 10, 100), "status": "ACTIVE", "icon": "📡"},
        {"label": "Validated", "value": m.get("validated", 0), "caption": "Passed checks", "progress": min(m.get("validated", 0) * 15, 100), "status": "READY" if m.get("validated", 0) else "WATCH", "icon": "✅"},
        {"label": "Pending", "value": m.get("pending", 0), "caption": "Awaiting confirmation", "progress": min(m.get("pending", 0) * 20, 100), "status": "WATCH" if m.get("pending", 0) else "READY", "icon": "⏳"},
        {"label": "Rejected", "value": m.get("rejected", 0), "caption": "Failed validation", "progress": min(m.get("rejected", 0) * 20, 100), "status": "WARNING" if m.get("rejected", 0) else "READY", "icon": "⛔"},
        {"label": "Success Rate", "value": f"{m.get('success_rate', 0):.0f}%", "caption": "Validation quality", "progress": m.get("success_rate", 0), "status": "READY" if m.get("success_rate", 0) >= 70 else "WARNING", "icon": "🎯"},
        {"label": "False Positive", "value": f"{m.get('false_positive_rate', 0):.0f}%", "caption": "Rejected share", "progress": 100 - m.get("false_positive_rate", 0), "status": "READY" if m.get("false_positive_rate", 0) <= 25 else "WARNING", "icon": "🧪"},
        {"label": "Avg Score", "value": f"{m.get('avg_validation_score', 0):.0f}", "caption": "Validation score", "progress": m.get("avg_validation_score", 0), "status": "READY" if m.get("avg_validation_score", 0) >= 70 else "WATCH", "icon": "📊"},
        {"label": "Avg R/R", "value": f"{m.get('avg_risk_reward', 0):.2f}", "caption": "Risk reward", "progress": min(m.get("avg_risk_reward", 0) * 30, 100), "status": "READY" if m.get("avg_risk_reward", 0) >= 1.5 else "WATCH", "icon": "⚖️"},
    ]
    render_metric_ribbon(cards)
