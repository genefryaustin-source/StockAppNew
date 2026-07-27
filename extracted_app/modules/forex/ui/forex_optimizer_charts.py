
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

from modules.forex.ui.forex_optimizer_summary import safe_float

def _base(height=320):
    fig = go.Figure()
    fig.update_layout(template="plotly_dark", height=height, margin=dict(l=8, r=8, t=38, b=8),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", legend=dict(orientation="h"))
    return fig

def render_allocation_donut(rows: List[Dict], title="Target Allocation", height=340):
    if st is None:
        return
    labels = [str(r.get("pair")) for r in rows]
    values = [safe_float(r.get("weight")) for r in rows]
    if go is None:
        st.bar_chart(dict(zip(labels, values)))
        return
    fig = _base(height)
    fig.add_trace(go.Pie(labels=labels, values=values, hole=.48))
    fig.update_layout(title=title)
    st.plotly_chart(fig, use_container_width=True)

def render_risk_budget_bar(rows: List[Dict], title="Risk Budget", height=330):
    if st is None:
        return
    ordered = sorted(rows, key=lambda r: safe_float(r.get("risk_budget")))
    labels = [str(r.get("pair")) for r in ordered]
    values = [safe_float(r.get("risk_budget")) for r in ordered]
    if go is None:
        st.bar_chart(dict(zip(labels, values)))
        return
    fig = _base(height)
    fig.add_trace(go.Bar(x=values, y=labels, orientation="h", name="Risk Budget"))
    fig.update_layout(title=title, xaxis_title="% Risk Budget")
    st.plotly_chart(fig, use_container_width=True)

def render_return_risk_scatter(rows: List[Dict], title="Return / Risk Map", height=340):
    if st is None:
        return
    x = [safe_float(r.get("risk_budget") or r.get("risk")) for r in rows]
    y = []
    for r in rows:
        er = r.get("expected_return")
        y.append(safe_float(er))
    if not any(y):
        y = [safe_float(r.get("sharpe")) * 2 for r in rows]
    labels = [str(r.get("pair")) for r in rows]
    sizes = [max(8, safe_float(r.get("weight")) * .9) for r in rows]
    if go is None:
        st.scatter_chart(pd.DataFrame({"risk": x, "return": y}))
        return
    fig = _base(height)
    fig.add_trace(go.Scatter(x=x, y=y, text=labels, mode="markers+text", marker=dict(size=sizes), textposition="top center"))
    fig.update_layout(title=title, xaxis_title="Risk Budget", yaxis_title="Expected Return / Sharpe Proxy")
    st.plotly_chart(fig, use_container_width=True)

def render_correlation_heatmap(rows: List[Dict], title="Allocation Correlation Proxy", height=360):
    if st is None:
        return
    labels = [str(r.get("pair")) for r in rows[:10]]
    if not labels:
        labels = ["EUR/USD", "USD/CHF", "GBP/USD"]
    matrix = []
    for i, a in enumerate(labels):
        row = []
        for j, b in enumerate(labels):
            if i == j:
                row.append(1.0)
            else:
                ac = set(a.replace("/", ""))
                bc = set(b.replace("/", ""))
                overlap = len(ac.intersection(bc))
                row.append(round(min(.85, .18 + overlap * .12), 2))
        matrix.append(row)
    if go is None:
        st.dataframe(pd.DataFrame(matrix, index=labels, columns=labels), use_container_width=True)
        return
    fig = _base(height)
    fig.add_trace(go.Heatmap(z=matrix, x=labels, y=labels, zmin=0, zmax=1, coloraxis="coloraxis"))
    fig.update_layout(title=title, coloraxis=dict(colorscale="RdBu"))
    st.plotly_chart(fig, use_container_width=True)

def render_optimizer_timeline(rows: List[Dict], title="Optimizer Timeline", height=300):
    if st is None:
        return
    labels = [str(r.get("pair")) for r in rows]
    weights = [safe_float(r.get("weight")) for r in rows]
    sharpe = [safe_float(r.get("sharpe")) * 20 for r in rows]
    if go is None:
        st.line_chart({"Weight": weights, "Sharpe": sharpe})
        return
    fig = _base(height)
    fig.add_trace(go.Scatter(x=labels, y=weights, mode="lines+markers", name="Weight"))
    fig.add_trace(go.Scatter(x=labels, y=sharpe, mode="lines+markers", name="Sharpe x20"))
    fig.update_layout(title=title)
    st.plotly_chart(fig, use_container_width=True)
