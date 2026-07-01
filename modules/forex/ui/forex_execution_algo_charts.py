
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

from modules.forex.ui.forex_execution_algo_summary import safe_float

def _base(height=320):
    fig = go.Figure()
    fig.update_layout(template="plotly_dark", height=height, margin=dict(l=8, r=8, t=38, b=8),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", legend=dict(orientation="h"))
    return fig

def render_algo_mix(rows: List[Dict], title="Algorithm Mix", height=300):
    if st is None: return
    counts = {}
    for row in rows:
        key = str(row.get("algorithm") or "SMART")
        counts[key] = counts.get(key, 0) + 1
    if go is None:
        st.bar_chart(counts)
        return
    fig = _base(height)
    fig.add_trace(go.Pie(labels=list(counts.keys()), values=list(counts.values()), hole=.45))
    fig.update_layout(title=title)
    st.plotly_chart(fig, use_container_width=True)

def render_slippage_bar(rows: List[Dict], title="Expected Slippage", height=320):
    if st is None: return
    ordered = sorted(rows, key=lambda r: safe_float(r.get("slippage_bps")))
    labels = [str(r.get("pair")) for r in ordered]
    values = [safe_float(r.get("slippage_bps")) for r in ordered]
    if go is None:
        st.bar_chart(dict(zip(labels, values)))
        return
    fig = _base(height)
    fig.add_trace(go.Bar(x=values, y=labels, orientation="h"))
    fig.update_layout(title=title, xaxis_title="bps")
    st.plotly_chart(fig, use_container_width=True)

def render_latency_timeline(rows: List[Dict], title="Routing Latency", height=300):
    if st is None: return
    x = [str(r.get("pair")) for r in rows]
    y = [safe_float(r.get("latency_ms")) for r in rows]
    if go is None:
        st.line_chart(y)
        return
    fig = _base(height)
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines+markers", name="Latency"))
    fig.update_layout(title=title, yaxis_title="ms")
    st.plotly_chart(fig, use_container_width=True)

def render_fill_progress(rows: List[Dict], title="Fill Progress", height=320):
    if st is None: return
    labels = [str(r.get("pair")) for r in rows]
    values = [safe_float(r.get("fill_rate")) for r in rows]
    if go is None:
        st.bar_chart(dict(zip(labels, values)))
        return
    fig = _base(height)
    fig.add_trace(go.Bar(x=labels, y=values, name="Fill %"))
    fig.update_layout(title=title, yaxis=dict(range=[0, 100]))
    st.plotly_chart(fig, use_container_width=True)
