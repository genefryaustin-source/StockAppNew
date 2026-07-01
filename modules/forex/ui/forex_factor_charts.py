
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

from modules.forex.ui.forex_factor_summary import FACTOR_KEYS, factor_score, aggregate_factor_scores

def _base(height=330):
    fig = go.Figure()
    fig.update_layout(template="plotly_dark", height=height, margin=dict(l=8,r=8,t=38,b=8),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", legend=dict(orientation="h"))
    return fig

def render_factor_heatmap(rows: List[Dict[str, Any]], title="Factor Heatmap", height=390):
    if st is None: return
    rows = rows or []
    z = [[factor_score(r, f) for f in FACTOR_KEYS] for r in rows]
    y = [str(r.get("pair") or r.get("symbol") or i) for i, r in enumerate(rows)]
    x = [f.title() for f in FACTOR_KEYS]
    if go is None:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        return
    fig = _base(height)
    fig.add_trace(go.Heatmap(z=z, x=x, y=y, coloraxis="coloraxis"))
    fig.update_layout(title=title, coloraxis=dict(colorscale="Viridis"))
    st.plotly_chart(fig, use_container_width=True)

def render_factor_bar_stack(rows: List[Dict[str, Any]], title="Aggregate Factor Scores", height=330):
    if st is None: return
    agg = aggregate_factor_scores(rows)
    ordered = sorted(agg.items(), key=lambda kv: kv[1])
    if go is None:
        st.dataframe(pd.DataFrame([{"Factor": k.title(), "Score": v} for k, v in ordered]), use_container_width=True, hide_index=True)
        return
    fig = _base(height)
    fig.add_trace(go.Bar(x=[v for _, v in ordered], y=[k.title() for k, _ in ordered], orientation="h"))
    fig.update_layout(title=title, xaxis=dict(range=[0,100]))
    st.plotly_chart(fig, use_container_width=True)

def render_factor_radar(rows: List[Dict[str, Any]], title="Factor Radar", height=340):
    if st is None: return
    agg = aggregate_factor_scores(rows)
    labels = [f.title() for f in FACTOR_KEYS]
    values = [agg.get(f, 0) for f in FACTOR_KEYS]
    if go is None:
        st.dataframe(pd.DataFrame({"Factor": labels, "Score": values}), use_container_width=True, hide_index=True)
        return
    fig = _base(height)
    fig.add_trace(go.Scatterpolar(r=values + [values[0]], theta=labels + [labels[0]], fill="toself", name="Factor Score"))
    fig.update_layout(title=title, polar=dict(radialaxis=dict(visible=True, range=[0,100])))
    st.plotly_chart(fig, use_container_width=True)

def render_factor_correlation(rows: List[Dict[str, Any]], title="Factor Correlation Matrix", height=390):
    if st is None: return
    if pd is None or go is None:
        render_factor_heatmap(rows, title, height)
        return
    data = pd.DataFrame([{f.title(): factor_score(r, f) for f in FACTOR_KEYS} for r in rows])
    corr = data.corr(numeric_only=True).fillna(0)
    fig = _base(height)
    fig.add_trace(go.Heatmap(z=corr.values, x=list(corr.columns), y=list(corr.index), zmin=-1, zmax=1, coloraxis="coloraxis"))
    fig.update_layout(title=title, coloraxis=dict(colorscale="RdBu"))
    st.plotly_chart(fig, use_container_width=True)

def render_factor_stability(rows: List[Dict[str, Any]], title="Model Stability", height=300):
    if st is None: return
    x = [str(r.get("pair") or i) for i, r in enumerate(rows)]
    stability = []
    for r in rows:
        vals = [factor_score(r, f) for f in FACTOR_KEYS]
        avg = sum(vals) / len(vals)
        dispersion = sum(abs(v - avg) for v in vals) / len(vals)
        stability.append(max(0, min(100, 100 - dispersion)))
    if go is None:
        st.line_chart(stability)
        return
    fig = _base(height)
    fig.add_trace(go.Scatter(x=x, y=stability, mode="lines+markers", name="Stability"))
    fig.update_layout(title=title, yaxis=dict(range=[0,100]))
    st.plotly_chart(fig, use_container_width=True)
