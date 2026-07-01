
from __future__ import annotations
from typing import Any, Dict, List
from modules.forex.ui.forex_regime_summary import normalize_regime
from modules.forex.ui.forex_ui_cards import render_metric_ribbon

def regime_status(regime: str) -> str:
    r = str(regime).upper()
    if "OFF" in r:
        return "WARNING"
    if "ON" in r:
        return "READY"
    return "WATCH"

def build_regime_cards(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    r = normalize_regime(payload)
    return [
        {"label": "Current Regime", "value": r["regime"].replace("_", "-"), "caption": "Macro state", "progress": r["confidence"], "status": regime_status(r["regime"]), "icon": "🌐"},
        {"label": "Confidence", "value": f"{r['confidence']:.0f}%", "caption": "Regime classifier", "progress": r["confidence"], "status": "READY" if r["confidence"] >= 70 else "WATCH", "icon": "🎯"},
        {"label": "Risk Appetite", "value": r["risk_appetite"], "caption": "Market tone", "progress": r["risk_score"], "status": regime_status(r["regime"]), "icon": "🛡️"},
        {"label": "Liquidity", "value": r["liquidity"], "caption": "Execution condition", "progress": 75, "status": "READY", "icon": "💧"},
        {"label": "Volatility", "value": r["volatility"], "caption": "Regime vol", "progress": 70, "status": "WATCH" if str(r["volatility"]).lower() in {"elevated", "high"} else "READY", "icon": "🌪️"},
        {"label": "Macro Score", "value": f"{r['macro_score']:.0f}", "caption": "Macro model", "progress": r["macro_score"], "status": "READY" if r["macro_score"] >= 65 else "WARNING", "icon": "🏦"},
    ]

def render_regime_kpi_ribbon(payload: Dict[str, Any]) -> None:
    render_metric_ribbon(build_regime_cards(payload))
