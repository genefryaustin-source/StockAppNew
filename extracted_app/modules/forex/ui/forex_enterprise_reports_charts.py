
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

from modules.forex.ui.forex_enterprise_reports_summary import safe_float, report_metrics

def _base(height=320):
    fig = go.Figure()
    fig.update_layout(template="plotly_dark", height=height, margin=dict(l=8, r=8, t=38, b=8),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", legend=dict(orientation="h"))
    return fig

def render_report_status_mix(rows: List[Dict], title="Report Status Mix", height=300):
    if st is None: return
    m = report_metrics(rows)
    labels = ["Generated", "Queued", "Pending", "Failed"]
    values = [m.get("generated", 0), m.get("queued", 0), m.get("pending", 0), m.get("failed", 0)]
    if go is None:
        st.bar_chart(dict(zip(labels, values)))
        return
    fig = _base(height)
    fig.add_trace(go.Pie(labels=labels, values=values, hole=.45))
    fig.update_layout(title=title)
    st.plotly_chart(fig, use_container_width=True)

def render_report_readiness_bar(rows: List[Dict], title="Report Readiness", height=330):
    if st is None: return
    ordered = sorted(rows, key=lambda r: safe_float(r.get("readiness")))
    labels = [str(r.get("report")) for r in ordered]
    values = [safe_float(r.get("readiness")) for r in ordered]
    if go is None:
        st.bar_chart(dict(zip(labels, values)))
        return
    fig = _base(height)
    fig.add_trace(go.Bar(x=values, y=labels, orientation="h"))
    fig.update_layout(title=title, xaxis=dict(range=[0, 100]))
    st.plotly_chart(fig, use_container_width=True)

def render_report_type_bar(rows: List[Dict], title="Report Type Coverage", height=310):
    if st is None: return
    counts = {}
    for row in rows:
        t = str(row.get("report_type") or "Executive")
        counts[t] = counts.get(t, 0) + 1
    if go is None:
        st.bar_chart(counts)
        return
    ordered = sorted(counts.items(), key=lambda kv: kv[1])
    fig = _base(height)
    fig.add_trace(go.Bar(x=[v for _, v in ordered], y=[k for k, _ in ordered], orientation="h"))
    fig.update_layout(title=title)
    st.plotly_chart(fig, use_container_width=True)

def render_report_timeline(rows: List[Dict], title="Reporting Timeline", height=300):
    if st is None: return
    labels = [str(r.get("report_type") or r.get("report")) for r in rows]
    readiness = [safe_float(r.get("readiness")) for r in rows]
    if go is None:
        st.line_chart(readiness)
        return
    fig = _base(height)
    fig.add_trace(go.Scatter(x=labels, y=readiness, mode="lines+markers", name="Readiness"))
    fig.update_layout(title=title, yaxis=dict(range=[0, 100]))
    st.plotly_chart(fig, use_container_width=True)
