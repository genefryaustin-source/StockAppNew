
from __future__ import annotations
from typing import Dict, List
from modules.forex.ui.forex_optimizer_summary import optimizer_metrics
from modules.forex.ui.forex_ui_cards import render_metric_ribbon

def render_optimizer_kpi_ribbon(payload: Dict, rows: List[Dict]) -> None:
    m = optimizer_metrics(payload, rows)
    cards = [
        {"label": "Allocations", "value": m.get("allocation_count", 0), "caption": "Target sleeves", "progress": min(m.get("allocation_count", 0) * 12, 100), "status": "ACTIVE", "icon": "📊"},
        {"label": "Total Weight", "value": f"{m.get('total_weight', 0):.0f}%", "caption": "Deployment", "progress": min(m.get("total_weight", 0), 100), "status": "READY", "icon": "💼"},
        {"label": "Avg Sharpe", "value": f"{m.get('avg_sharpe', 0):.2f}", "caption": "Risk-adjusted", "progress": min(abs(m.get("avg_sharpe", 0)) * 35, 100), "status": "READY" if m.get("avg_sharpe", 0) >= 1 else "WATCH", "icon": "📈"},
        {"label": "Max Position", "value": f"{m.get('max_position', 0):.0f}%", "caption": "Concentration", "progress": max(0, 100 - m.get("max_position", 0)), "status": "READY" if m.get("max_position", 0) <= 30 else "WARNING", "icon": "🛡️"},
        {"label": "Diversification", "value": f"{m.get('diversification_score', 0):.0f}", "caption": "Portfolio balance", "progress": m.get("diversification_score", 0), "status": "READY" if m.get("diversification_score", 0) >= 65 else "WATCH", "icon": "🧩"},
        {"label": "Expected Return", "value": m.get("expected_return") or "N/A", "caption": "Optimizer output", "progress": 75, "status": "ACTIVE", "icon": "⚡"},
        {"label": "Portfolio Risk", "value": m.get("portfolio_risk") or "Managed", "caption": "Risk target", "progress": 75, "status": "READY", "icon": "⚖️"},
        {"label": "Status", "value": m.get("optimizer_status", "READY"), "caption": "Optimizer engine", "progress": 100, "status": m.get("optimizer_status", "READY"), "icon": "🟢"},
    ]
    render_metric_ribbon(cards)
