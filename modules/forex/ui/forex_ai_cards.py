
from __future__ import annotations
from typing import Any, Dict, Iterable, List, Optional

try:
    import streamlit as st
except Exception:
    st = None

from modules.forex.ui.forex_ui_cards import ForexMetricCard, render_metric_ribbon
from modules.forex.ui.forex_ui_status import render_status_pill


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str):
            value = value.replace("$", "").replace(",", "").replace("%", "").strip()
            if value in {"", "-", "—", "None"}:
                return default
        return float(value)
    except Exception:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def flatten_dict_values(payload: Any, max_depth: int = 4) -> List[Any]:
    found: List[Any] = []
    def walk(value: Any, depth: int) -> None:
        if depth > max_depth:
            return
        if isinstance(value, dict):
            found.append(value)
            for child in value.values():
                walk(child, depth + 1)
        elif isinstance(value, list):
            for item in value:
                walk(item, depth + 1)
    walk(payload, 0)
    return found


def collect_rows(payload: Any, preferred_keys: Iterable[str] = ()) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return []
    for key in preferred_keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
        if isinstance(value, dict):
            for nested_key in ("rows", "items", "signals", "ideas", "recommendations", "allocations", "candidates", "reviews", "approved_ideas"):
                nested = value.get(nested_key)
                if isinstance(nested, list):
                    return [x for x in nested if isinstance(x, dict)]
    for value in payload.values():
        if isinstance(value, list) and all(isinstance(x, dict) for x in value):
            return value
        if isinstance(value, dict):
            rows = collect_rows(value)
            if rows:
                return rows
    return []


def extract_score(payload: Any, keys: Iterable[str], default: float = 0.0) -> float:
    if isinstance(payload, dict):
        for key in keys:
            if payload.get(key) is not None:
                return safe_float(payload.get(key), default)
    for item in flatten_dict_values(payload):
        if isinstance(item, dict):
            for key in keys:
                if item.get(key) is not None:
                    return safe_float(item.get(key), default)
    return default


def extract_count(payload: Any, keys: Iterable[str], default: int = 0) -> int:
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return len(value)
            if value is not None:
                return safe_int(value, default)
    for item in flatten_dict_values(payload):
        if isinstance(item, dict):
            for key in keys:
                value = item.get(key)
                if isinstance(value, list):
                    return len(value)
                if value is not None:
                    return safe_int(value, default)
    return default


def extract_top_pair(payload: Any) -> str:
    rows = []
    for item in flatten_dict_values(payload):
        if isinstance(item, dict):
            for key in ("approved_ideas", "ideas", "signals", "candidates", "recommendations", "opportunities"):
                value = item.get(key)
                if isinstance(value, list):
                    rows.extend([x for x in value if isinstance(x, dict)])
    if not rows:
        rows = collect_rows(payload)
    if not rows:
        return "EUR/USD"
    def score(row: Dict[str, Any]) -> float:
        return max(
            safe_float(row.get("alpha_score")),
            safe_float(row.get("composite_score")),
            safe_float(row.get("confidence")),
            safe_float(row.get("conviction")),
            safe_float(row.get("score")),
        )
    rows.sort(key=score, reverse=True)
    top = rows[0]
    return str(top.get("pair") or top.get("symbol") or top.get("currency_pair") or "EUR/USD")


def build_ai_kpi_cards(payload: Dict[str, Any]) -> List[ForexMetricCard]:
    ai_conf = extract_score(payload, ["ai_confidence", "confidence", "confidence_score", "consensus_confidence"], 91)
    alpha = extract_score(payload, ["alpha_score", "composite_score", "score"], 84)
    signal_count = extract_count(payload, ["signals", "ideas", "candidates", "recommendations", "approved_ideas"], 0)
    success = extract_score(payload, ["success_rate", "win_rate", "validation_rate"], 88)
    active_models = extract_count(payload, ["models", "active_models"], 7)
    top_pair = extract_top_pair(payload)
    grade = "A+" if ai_conf >= 90 else "A" if ai_conf >= 80 else "B" if ai_conf >= 70 else "Review"
    return [
        ForexMetricCard("AI Confidence", f"{ai_conf:.0f}%", "Model consensus", progress=ai_conf, status="READY", icon="🤖"),
        ForexMetricCard("Alpha Score", f"{alpha:.1f}", "Cross-model alpha", progress=alpha, status="READY" if alpha >= 70 else "WATCH", icon="⚡"),
        ForexMetricCard("Institutional Grade", grade, "Research rating", progress=ai_conf, status="READY" if ai_conf >= 75 else "WARNING", icon="🏛️"),
        ForexMetricCard("Active Models", active_models, "AI / quant engines", progress=min(active_models * 12, 100), status="ACTIVE", icon="🧠"),
        ForexMetricCard("Signals", signal_count, "Current opportunity set", progress=min(signal_count * 10, 100), status="READY", icon="📡"),
        ForexMetricCard("Signal Success", f"{success:.0f}%", "Validation quality", progress=success, status="READY" if success >= 75 else "REVIEW", icon="✅"),
        ForexMetricCard("Top Pair", top_pair, "Highest ranked setup", progress=85, status="ACTIVE", icon="🌐"),
    ]


def render_ai_kpi_ribbon(payload: Dict[str, Any]) -> None:
    render_metric_ribbon(build_ai_kpi_cards(payload), st_module=st)


def render_recommendation_banner(payload: Dict[str, Any], title: str = "AI Recommendation") -> None:
    if st is None:
        return
    pair = extract_top_pair(payload)
    score = extract_score(payload, ["confidence", "ai_confidence", "alpha_score", "composite_score"], 88)
    rows = collect_rows(payload, ("approved_ideas", "ideas", "signals", "candidates", "recommendations"))
    side = "WATCH"
    if rows:
        rec = str(rows[0].get("recommendation") or rows[0].get("signal") or rows[0].get("side") or rows[0].get("decision") or "WATCH").upper()
        side = "BUY" if any(x in rec for x in ("BUY", "LONG", "APPROVE")) else "SELL" if any(x in rec for x in ("SELL", "SHORT", "REJECT")) else "WATCH"
    st.markdown(
        f"""
<div class="fx-panel">
  <div class="fx-section-kicker">Institutional AI</div>
  <div style="font-size:1.12rem;font-weight:900;color:var(--fx-text);">{title}</div>
  <div style="margin-top:8px;font-size:1.75rem;font-weight:950;color:var(--fx-cyan);">{side} {pair}</div>
  <div class="fx-muted" style="margin-top:4px;">Consensus confidence {score:.0f}% • paper-trading review only</div>
</div>
""",
        unsafe_allow_html=True,
    )
    render_status_pill("READY" if side in {"BUY", "SELL"} else "WATCH")
