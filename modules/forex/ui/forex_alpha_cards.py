
from __future__ import annotations
from typing import Dict, List
from modules.forex.ui.forex_alpha_summary import alpha_metrics
from modules.forex.ui.forex_ui_cards import render_metric_ribbon

def render_alpha_kpi_ribbon(rows: List[Dict]) -> None:
    m = alpha_metrics(rows)
    cards = [
        {"label": "Alpha Ideas", "value": m.get("total", 0), "caption": "Ranked opportunities", "progress": min(m.get("total", 0) * 10, 100), "status": "ACTIVE", "icon": "⚡"},
        {"label": "Approved", "value": m.get("approved", 0), "caption": "Above threshold", "progress": min(m.get("approved", 0) * 15, 100), "status": "READY" if m.get("approved", 0) else "WATCH", "icon": "✅"},
        {"label": "Buy Signals", "value": m.get("buy", 0), "caption": "Long setups", "progress": min(m.get("buy", 0) * 15, 100), "status": "READY", "icon": "🟢"},
        {"label": "Sell Signals", "value": m.get("sell", 0), "caption": "Short setups", "progress": min(m.get("sell", 0) * 15, 100), "status": "READY", "icon": "🔴"},
        {"label": "Avg Alpha", "value": f"{m.get('avg_alpha', 0):.0f}", "caption": "Mean score", "progress": m.get("avg_alpha", 0), "status": "READY" if m.get("avg_alpha", 0) >= 70 else "WATCH", "icon": "📊"},
        {"label": "Avg Confidence", "value": f"{m.get('avg_confidence', 0):.0f}%", "caption": "Mean confidence", "progress": m.get("avg_confidence", 0), "status": "READY" if m.get("avg_confidence", 0) >= 70 else "WARNING", "icon": "🎯"},
        {"label": "Avg R/R", "value": f"{m.get('avg_risk_reward', 0):.2f}", "caption": "Risk reward", "progress": min(m.get("avg_risk_reward", 0) * 30, 100), "status": "READY" if m.get("avg_risk_reward", 0) >= 1.5 else "WATCH", "icon": "⚖️"},
        {"label": "Top Setup", "value": f"{m.get('top_signal', 'WATCH')} {m.get('top_pair', 'EUR/USD')}", "caption": "Highest alpha", "progress": 90, "status": "ACTIVE", "icon": "🏆"},
    ]
    render_metric_ribbon(cards)
