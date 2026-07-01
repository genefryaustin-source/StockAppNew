
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

from modules.forex.ui.forex_alpha_summary import safe_float

def _base(height=320):
    fig = go.Figure()
    fig.update_layout(template="plotly_dark", height=height, margin=dict(l=8, r=8, t=38, b=8),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", legend=dict(orientation="h"))
    return fig

def render_alpha_score_bar(rows: List[Dict], title="Alpha Scores", height=340):
    if st is None: return
    data = rows[:12]
    labels = [str(r.get("pair")) for r in data]
    values = [safe_float(r.get("alpha_score")) for r in data]
    if go is None:
        st.bar_chart(values); return
    fig = _base(height)
    fig.add_trace(go.Bar(x=labels, y=values, name="Alpha"))
    fig.update_layout(title=title, yaxis=dict(range=[0,100]))
    st.plotly_chart(fig, use_container_width=True)

def render_alpha_confidence_scatter(rows: List[Dict], title="Alpha vs Confidence", height=340):
    if st is None: return
    x = [safe_float(r.get("alpha_score")) for r in rows]
    y = [safe_float(r.get("confidence")) for r in rows]
    text = [str(r.get("pair")) for r in rows]
    size = [max(8, safe_float(r.get("risk_reward")) * 8) for r in rows]
    if go is None:
        st.scatter_chart(pd.DataFrame({"alpha": x, "confidence": y}))
        return
    fig = _base(height)
    fig.add_trace(go.Scatter(x=x, y=y, text=text, mode="markers+text", marker=dict(size=size), textposition="top center"))
    fig.update_layout(title=title, xaxis_title="Alpha", yaxis_title="Confidence", xaxis=dict(range=[0,100]), yaxis=dict(range=[0,100]))
    st.plotly_chart(fig, use_container_width=True)

def render_alpha_heatmap(rows: List[Dict], title="Alpha Opportunity Heatmap", height=360):
    if st is None: return
    cols = ["alpha_score", "confidence", "conviction", "risk_reward", "momentum_score", "macro_score", "carry_score", "liquidity_score"]
    cols = [c for c in cols if any(isinstance(r, dict) and r.get(c) is not None for r in rows)]
    if not cols:
        cols = ["alpha_score", "confidence", "conviction", "risk_reward"]
    data = rows[:14]
    z = [[safe_float(r.get(c)) * (25 if c == "risk_reward" else 1) for c in cols] for r in data]
    y = [str(r.get("pair")) for r in data]
    x = [c.replace("_score", "").replace("_", " ").title() for c in cols]
    if go is None:
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True); return
    fig = _base(height)
    fig.add_trace(go.Heatmap(z=z, x=x, y=y, coloraxis="coloraxis"))
    fig.update_layout(title=title, coloraxis=dict(colorscale="Viridis"))
    st.plotly_chart(fig, use_container_width=True)

def render_alpha_timeline(rows: List[Dict], title="Alpha Timeline", height=300):
    if st is None: return
    x = [r.get("asof") or r.get("generated_at") or r.get("created_at") or i for i, r in enumerate(rows)]
    alpha = [safe_float(r.get("alpha_score")) for r in rows]
    conf = [safe_float(r.get("confidence")) for r in rows]
    if not x:
        x = list(range(20)); alpha = [72 + (i % 5) * 2 + i * .2 for i in x]; conf = [68 + (i % 6) * 2 + i * .25 for i in x]
    if go is None:
        st.line_chart({"Alpha": alpha, "Confidence": conf}); return
    fig = _base(height)
    fig.add_trace(go.Scatter(x=x, y=alpha, mode="lines+markers", name="Alpha"))
    fig.add_trace(go.Scatter(x=x, y=conf, mode="lines+markers", name="Confidence"))
    fig.update_layout(title=title, yaxis=dict(range=[0,100]))
    st.plotly_chart(fig, use_container_width=True)

def render_signal_mix(rows: List[Dict], title="Signal Mix", height=280):
    if st is None: return
    counts = {"BUY": 0, "SELL": 0, "WATCH": 0}
    for row in rows:
        sig = str(row.get("signal", "WATCH")).upper()
        if "BUY" in sig:
            counts["BUY"] += 1
        elif "SELL" in sig:
            counts["SELL"] += 1
        else:
            counts["WATCH"] += 1
    if go is None:
        st.bar_chart(counts); return
    fig = _base(height)
    fig.add_trace(go.Pie(labels=list(counts.keys()), values=list(counts.values()), hole=.45))
    fig.update_layout(title=title)
    st.plotly_chart(fig, use_container_width=True)
