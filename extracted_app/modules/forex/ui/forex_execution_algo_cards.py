
from __future__ import annotations
from typing import Dict, List
from modules.forex.ui.forex_execution_algo_summary import execution_metrics
from modules.forex.ui.forex_ui_cards import render_metric_ribbon

def render_execution_algo_kpi_ribbon(rows: List[Dict]) -> None:
    m = execution_metrics(rows)
    cards = [
        {"label": "Algorithms", "value": m.get("total_algos", 0), "caption": "Routes monitored", "progress": min(m.get("total_algos", 0) * 15, 100), "status": "ACTIVE", "icon": "⚙️"},
        {"label": "Ready", "value": m.get("ready", 0), "caption": "Queued routes", "progress": min(m.get("ready", 0) * 20, 100), "status": "READY", "icon": "🟢"},
        {"label": "Active", "value": m.get("active", 0), "caption": "Working algos", "progress": min(m.get("active", 0) * 20, 100), "status": "ACTIVE" if m.get("active", 0) else "WATCH", "icon": "🚦"},
        {"label": "Completed", "value": m.get("completed", 0), "caption": "Filled routes", "progress": min(m.get("completed", 0) * 20, 100), "status": "READY", "icon": "✅"},
        {"label": "Avg Slippage", "value": f"{m.get('avg_slippage_bps', 0):.2f} bps", "caption": "Execution cost", "progress": max(0, 100 - m.get("avg_slippage_bps", 0) * 20), "status": "READY" if m.get("avg_slippage_bps", 0) <= 1 else "WARNING", "icon": "📉"},
        {"label": "Avg Latency", "value": f"{m.get('avg_latency_ms', 0):.0f} ms", "caption": "Routing speed", "progress": max(0, 100 - m.get("avg_latency_ms", 0) / 3), "status": "READY" if m.get("avg_latency_ms", 0) <= 150 else "WARNING", "icon": "⚡"},
        {"label": "Fill Rate", "value": f"{m.get('avg_fill_rate', 0):.0f}%", "caption": "Completion", "progress": m.get("avg_fill_rate", 0), "status": "ACTIVE", "icon": "📊"},
        {"label": "Mode", "value": m.get("execution_mode", "PAPER"), "caption": "Broker safety", "progress": 100, "status": "DISABLED" if m.get("execution_mode") == "PAPER" else "READY", "icon": "🔒"},
    ]
    render_metric_ribbon(cards)
