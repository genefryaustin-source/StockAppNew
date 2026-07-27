
from __future__ import annotations
from typing import Any, Dict, List
from modules.forex.ui.forex_factor_summary import FACTOR_KEYS, aggregate_factor_scores
from modules.forex.ui.forex_ui_cards import render_metric_ribbon

def factor_status(score: float) -> str:
    if score >= 75:
        return "READY"
    if score >= 60:
        return "WATCH"
    return "WARNING"

def build_factor_cards(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    agg = aggregate_factor_scores(rows)
    icons = {
        "carry": "💵", "momentum": "📈", "value": "⚖️", "quality": "🏛️",
        "liquidity": "💧", "volatility": "🌪️", "macro": "🌐", "sentiment": "🗞️",
    }
    cards = []
    for factor in FACTOR_KEYS:
        score = agg.get(factor, 0.0)
        cards.append({
            "label": factor.title(),
            "value": f"{score:.0f}",
            "caption": "Factor score",
            "progress": score,
            "status": factor_status(score),
            "icon": icons.get(factor, "📊"),
        })
    return cards

def render_factor_kpi_ribbon(rows: List[Dict[str, Any]]) -> None:
    render_metric_ribbon(build_factor_cards(rows))
