
from __future__ import annotations
from typing import Dict, List

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

from modules.forex.ui.forex_signal_validation_summary import safe_float, validation_metrics

def _base(height=320):
    fig = go.Figure()
    fig.update_layout(template="plotly_dark", height=height, margin=dict(l=8, r=8, t=38, b=8),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", legend=dict(orientation="h"))
    return fig

def render_validation_gauge(
    score: float,
    confidence: float,
):
    value = max(score, confidence)

    if st is None:
        return

    if go is None:
        st.metric("Signal Quality", f"{value:.0f}%")
        return

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            number={"suffix": "%"},
            title={"text": "Signal Quality"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#20d6ff"},
                "steps": [
                    {"range": [0, 50], "color": "rgba(255,77,109,0.18)"},
                    {"range": [50, 75], "color": "rgba(255,209,102,0.18)"},
                    {"range": [75, 100], "color": "rgba(47,245,141,0.18)"},
                ],
            },
        )
    )

    fig.update_layout(
        template="plotly_dark",
        height=280,
        margin=dict(l=10, r=10, t=40, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
    )

    st.plotly_chart(fig, use_container_width=True)

def render_validation_status_mix(rows: List[Dict], title="Validation Mix", height=280):
    if st is None:
        return
    m = validation_metrics(rows)
    labels = ["Validated", "Pending", "Rejected"]
    values = [m.get("validated", 0), m.get("pending", 0), m.get("rejected", 0)]
    if go is None:
        st.bar_chart(dict(zip(labels, values)))
        return
    fig = _base(height)
    fig.add_trace(go.Pie(labels=labels, values=values, hole=.45))
    fig.update_layout(title=title)
    st.plotly_chart(fig, use_container_width=True)

def render_validation_score_bar(rows: List[Dict], title="Validation Scores", height=340):
    if st is None:
        return
    data = rows[:15]
    labels = [str(r.get("pair")) for r in data]
    values = [safe_float(r.get("validation_score")) for r in data]
    if go is None:
        st.bar_chart(values)
        return
    fig = _base(height)
    fig.add_trace(go.Bar(x=labels, y=values, name="Validation Score"))
    fig.update_layout(title=title, yaxis=dict(range=[0,100]))
    st.plotly_chart(fig, use_container_width=True)

def render_validation_timeline(rows: List[Dict], title="Validation Timeline", height=310):
    if st is None:
        return
    x = [r.get("asof") or r.get("generated_at") or r.get("created_at") or i for i, r in enumerate(rows)]
    score = [safe_float(r.get("validation_score")) for r in rows]
    conf = [safe_float(r.get("confidence")) for r in rows]
    if not x:
        x = list(range(20)); score = [72 + (i % 5) * 2 + i * .2 for i in x]; conf = [68 + (i % 6) * 2 + i * .25 for i in x]
    if go is None:
        st.line_chart({"Validation": score, "Confidence": conf})
        return
    fig = _base(height)
    fig.add_trace(go.Scatter(x=x, y=score, mode="lines+markers", name="Validation"))
    fig.add_trace(go.Scatter(x=x, y=conf, mode="lines+markers", name="Confidence"))
    fig.update_layout(title=title, yaxis=dict(range=[0,100]))
    st.plotly_chart(fig, use_container_width=True)

def render_validation_heatmap(rows: List[Dict], title="Validation Heatmap", height=360):
    if st is None:
        return
    cols = ["validation_score", "confidence", "risk_reward", "alpha_score", "composite_score", "quality_score"]
    cols = [c for c in cols if any(isinstance(r, dict) and r.get(c) is not None for r in rows)]
    if not cols:
        cols = ["validation_score", "confidence", "risk_reward"]
    data = rows[:14]
    z = [[safe_float(r.get(c)) * (25 if c == "risk_reward" else 1) for c in cols] for r in data]
    y = [str(r.get("pair")) for r in data]
    x = [c.replace("_score", "").replace("_", " ").title() for c in cols]
    if go is None:
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
        return
    fig = _base(height)
    fig.add_trace(go.Heatmap(z=z, x=x, y=y, coloraxis="coloraxis"))
    fig.update_layout(title=title, coloraxis=dict(colorscale="Viridis"))
    st.plotly_chart(fig, use_container_width=True)
