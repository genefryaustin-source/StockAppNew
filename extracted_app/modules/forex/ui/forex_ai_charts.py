
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

from modules.forex.ui.forex_ai_cards import safe_float


def _base(height: int = 300):
    fig = go.Figure()
    fig.update_layout(template="plotly_dark", height=height, margin=dict(l=8, r=8, t=32, b=8),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig


def render_gauge(value: Any, title: str = "Score", height: int = 280) -> None:
    if st is None:
        return
    val = max(0, min(100, safe_float(value)))
    if go is None:
        st.metric(title, f"{val:.1f}")
        return
    fig = go.Figure(go.Indicator(mode="gauge+number", value=val, title={"text": title},
        gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#20d6ff"},
               "steps": [{"range": [0, 50], "color": "rgba(255,77,109,0.18)"},
                         {"range": [50, 75], "color": "rgba(255,209,102,0.18)"},
                         {"range": [75, 100], "color": "rgba(47,245,141,0.18)"}]}))
    fig.update_layout(template="plotly_dark", height=height, margin=dict(l=10, r=10, t=42, b=8),
                      paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)


def render_factor_bars(factors: Dict[str, Any], title: str = "Factor Scores", height: int = 320) -> None:
    if st is None:
        return
    rows = []
    for key, value in (factors or {}).items():
        score = value.get("score") if isinstance(value, dict) else value
        rows.append((str(key).replace("_", " ").title(), safe_float(score)))
    if not rows:
        rows = [("Carry", 72), ("Momentum", 81), ("Value", 63), ("Quality", 77), ("Volatility", 58), ("Liquidity", 86), ("Macro", 74)]
    rows.sort(key=lambda x: x[1])
    if go is None:
        st.dataframe(pd.DataFrame(rows, columns=["Factor", "Score"]), use_container_width=True, hide_index=True)
        return
    fig = _base(height)
    fig.add_trace(go.Bar(x=[r[1] for r in rows], y=[r[0] for r in rows], orientation="h"))
    fig.update_layout(title=title, xaxis=dict(range=[0, 100]))
    st.plotly_chart(fig, use_container_width=True)


def render_allocation_pie(rows: List[Dict[str, Any]], title: str = "Recommended Allocation", height: int = 320) -> None:
    if st is None:
        return
    labels, values = [], []
    for row in rows or []:
        labels.append(str(row.get("pair") or row.get("strategy") or row.get("bucket") or row.get("asset") or "FX"))
        values.append(abs(safe_float(row.get("weight") or row.get("allocation") or row.get("allocation_pct") or row.get("capital"), 0)))
    if not labels:
        labels, values = ["EUR/USD", "USD/CHF", "GBP/USD", "Cash"], [30, 25, 20, 25]
    if go is None:
        st.dataframe(pd.DataFrame({"Label": labels, "Value": values}), use_container_width=True, hide_index=True)
        return
    fig = _base(height)
    fig.add_trace(go.Pie(labels=labels, values=values, hole=0.46))
    fig.update_layout(title=title)
    st.plotly_chart(fig, use_container_width=True)


def render_score_timeline(rows: List[Dict[str, Any]], title: str = "Signal Timeline", height: int = 280) -> None:
    if st is None:
        return
    x, y = [], []
    for i, row in enumerate(rows or []):
        x.append(row.get("asof") or row.get("generated_at") or row.get("created_at") or i)
        y.append(safe_float(row.get("confidence") or row.get("score") or row.get("alpha_score") or row.get("composite_score"), 0))
    if not x:
        x = list(range(20)); y = [66 + ((i % 7) * 3) + (i * 0.7) for i in x]
    if go is None:
        st.line_chart(y)
        return
    fig = _base(height)
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines+markers", fill="tozeroy"))
    fig.update_layout(title=title, yaxis=dict(range=[0, 100]))
    st.plotly_chart(fig, use_container_width=True)


def render_heatmap_from_rows(rows: List[Dict[str, Any]], title: str = "Score Heatmap", height: int = 340) -> None:
    if st is None:
        return
    numeric_cols = []
    for row in rows or []:
        for key, val in row.items():
            if isinstance(val, (int, float)) and key not in numeric_cols:
                numeric_cols.append(key)
    numeric_cols = numeric_cols[:8]
    if not rows or not numeric_cols:
        rows = [{"pair": "EUR/USD", "alpha": 82, "momentum": 78, "quality": 75}, {"pair": "USD/CHF", "alpha": 79, "momentum": 71, "quality": 82}]
        numeric_cols = ["alpha", "momentum", "quality"]
    if go is None:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        return
    fig = _base(height)
    z = [[safe_float(row.get(col)) for col in numeric_cols] for row in rows[:12]]
    y = [str(row.get("pair") or row.get("symbol") or row.get("strategy") or i) for i, row in enumerate(rows[:12])]
    fig.add_trace(go.Heatmap(z=z, x=numeric_cols, y=y, coloraxis="coloraxis"))
    fig.update_layout(title=title, coloraxis=dict(colorscale="Viridis"))
    st.plotly_chart(fig, use_container_width=True)
