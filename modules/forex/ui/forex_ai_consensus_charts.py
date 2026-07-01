
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


def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _base(height=320):
    fig = go.Figure()
    fig.update_layout(
        template="plotly_dark",
        height=height,
        margin=dict(l=8, r=8, t=38, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h"),
    )
    return fig


def render_consensus_gauge(consensus: Dict, title: str = "AI Consensus", height: int = 280):
    if st is None:
        return
    value = safe_float(consensus.get("weighted_confidence"))
    if go is None:
        st.metric(title, f"{value:.0f}%")
        return
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            number={"suffix": "%"},
            title={"text": title},
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
    fig.update_layout(template="plotly_dark", height=height, margin=dict(l=10, r=10, t=42, b=8), paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)


def render_vote_mix(consensus: Dict, title: str = "Vote Mix", height: int = 280):
    if st is None:
        return
    counts = consensus.get("vote_counts", {}) or {}
    labels = ["BUY", "SELL", "WATCH", "HOLD"]
    values = [counts.get(label, 0) for label in labels]
    if go is None:
        st.bar_chart(dict(zip(labels, values)))
        return
    fig = _base(height)
    fig.add_trace(go.Pie(labels=labels, values=values, hole=.45))
    fig.update_layout(title=title)
    st.plotly_chart(fig, use_container_width=True)


def render_model_confidence_bar(consensus: Dict, title: str = "Model Confidence", height: int = 330):
    if st is None:
        return
    rows = consensus.get("votes", []) or []
    labels = [str(r.get("Model")) for r in rows]
    values = [safe_float(r.get("Confidence")) for r in rows]
    if go is None:
        st.bar_chart(dict(zip(labels, values)))
        return
    fig = _base(height)
    fig.add_trace(go.Bar(x=values, y=labels, orientation="h"))
    fig.update_layout(title=title, xaxis=dict(range=[0, 100]))
    st.plotly_chart(fig, use_container_width=True)


def render_attribution_bar(consensus: Dict, title: str = "Confidence Attribution", height: int = 330):
    if st is None:
        return
    rows = consensus.get("attribution", []) or []
    labels = [str(r.get("Model")) for r in rows]
    values = [safe_float(r.get("Contribution")) for r in rows]
    if go is None:
        st.bar_chart(dict(zip(labels, values)))
        return
    fig = _base(height)
    fig.add_trace(go.Bar(x=values, y=labels, orientation="h"))
    fig.update_layout(title=title)
    st.plotly_chart(fig, use_container_width=True)
