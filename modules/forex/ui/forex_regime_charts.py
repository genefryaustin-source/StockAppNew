
from __future__ import annotations
from typing import Any, Dict, List

try:
    import streamlit as st
    import pandas as pd
except Exception:
    st = None
    pd = None

try:
    import plotly.graph_objects as go
except Exception:
    go = None

from modules.forex.ui.forex_regime_summary import safe_float, normalize_regime

def _base(height=320):
    fig = go.Figure()
    fig.update_layout(template="plotly_dark", height=height, margin=dict(l=8, r=8, t=38, b=8),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", legend=dict(orientation="h"))
    return fig

def render_regime_gauge(payload: Dict[str, Any], title="Regime Confidence", height=280):
    if st is None: return
    r = normalize_regime(payload)
    val = r["confidence"]
    if go is None:
        st.metric(title, f"{val:.0f}%")
        return
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=val,
        title={"text": title},
        gauge={"axis": {"range": [0, 100]},
               "bar": {"color": "#20d6ff"},
               "steps": [
                   {"range": [0, 50], "color": "rgba(255,77,109,0.18)"},
                   {"range": [50, 75], "color": "rgba(255,209,102,0.18)"},
                   {"range": [75, 100], "color": "rgba(47,245,141,0.18)"},
               ]},
    ))
    fig.update_layout(template="plotly_dark", height=height, margin=dict(l=10, r=10, t=42, b=8), paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

def render_transition_probability(payload: Dict[str, Any], title="Transition Probability", height=300):
    if st is None: return
    trans = normalize_regime(payload)["transition_probability"]
    rows = sorted([(str(k), safe_float(v)) for k, v in trans.items()], key=lambda x: x[1])
    if go is None:
        st.dataframe(pd.DataFrame(rows, columns=["Regime", "Probability"]), use_container_width=True, hide_index=True)
        return
    fig = _base(height)
    fig.add_trace(go.Bar(x=[v for _, v in rows], y=[k for k, _ in rows], orientation="h"))
    fig.update_layout(title=title, xaxis=dict(range=[0, 100]))
    st.plotly_chart(fig, use_container_width=True)

def render_regime_timeline(rows: List[Dict[str, Any]], title="Regime History", height=310):
    if st is None: return
    x = [r.get("period") or r.get("date") or r.get("asof") or i for i, r in enumerate(rows or [])]
    y = [safe_float(r.get("confidence") or r.get("score") or 0) for r in rows or []]
    label = [str(r.get("regime") or r.get("state") or "") for r in rows or []]
    if not x:
        x = list(range(10)); y = [62, 66, 70, 68, 73, 75, 78, 76, 80, 82]; label = ["Risk-Off"] * 10
    if go is None:
        st.line_chart(y)
        return
    fig = _base(height)
    fig.add_trace(go.Scatter(x=x, y=y, text=label, mode="lines+markers", name="Confidence"))
    fig.update_layout(title=title, yaxis=dict(range=[0, 100]))
    st.plotly_chart(fig, use_container_width=True)

def render_macro_driver_bar(rows: List[Dict[str, Any]], title="Macro Driver Impact", height=310):
    if st is None: return
    labels = [str(r.get("driver") or r.get("name") or f"Driver {i}") for i, r in enumerate(rows or [])]
    scores = [safe_float(r.get("score") or r.get("impact_score") or r.get("confidence") or (75 if str(r.get("status", "")).upper() in {"READY", "HAWKISH", "DEFENSIVE"} else 62)) for r in rows or []]
    if not labels:
        labels = ["Fed", "ECB", "BoJ", "SNB", "Liquidity", "Volatility"]; scores = [72, 58, 61, 79, 68, 74]
    ordered = sorted(zip(labels, scores), key=lambda x: x[1])
    if go is None:
        st.dataframe(pd.DataFrame(ordered, columns=["Driver", "Score"]), use_container_width=True, hide_index=True)
        return
    fig = _base(height)
    fig.add_trace(go.Bar(x=[v for _, v in ordered], y=[k for k, _ in ordered], orientation="h"))
    fig.update_layout(title=title, xaxis=dict(range=[0, 100]))
    st.plotly_chart(fig, use_container_width=True)
