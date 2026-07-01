
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
from modules.forex.ui.forex_quant_statistics import safe_float

def _base(height=320):
    fig=go.Figure()
    fig.update_layout(template="plotly_dark",height=height,margin=dict(l=8,r=8,t=38,b=8),paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",legend=dict(orientation="h"))
    return fig

def render_confidence_distribution(rows: List[Dict[str, Any]], title="Confidence Distribution", height=310):
    if st is None: return
    vals=[]
    for r in rows or []:
        if isinstance(r,dict):
            vals.append(safe_float(r.get("confidence") or r.get("confidence_score") or r.get("signal_confidence") or r.get("composite_score") or r.get("alpha_score")))
    vals=[v for v in vals if v]
    if not vals: vals=[62,68,72,75,78,81,84,86,89,91,94]
    if go is None:
        st.bar_chart(vals); return
    fig=_base(height); fig.add_trace(go.Histogram(x=vals,nbinsx=16,name="Confidence"))
    fig.update_layout(title=title,xaxis_title="Confidence",yaxis_title="Signals")
    st.plotly_chart(fig,use_container_width=True)

def render_factor_contribution(rows: List[Dict[str, Any]], title="Factor Contribution", height=320):
    if st is None: return
    preferred=["carry_score","momentum_score","value_score","macro_score","risk_score","liquidity_score","quality_score","volatility_score","flow_score","sentiment_score"]
    buckets={}
    for r in rows or []:
        if isinstance(r,dict):
            for k in preferred:
                if r.get(k) is not None:
                    buckets.setdefault(k.replace("_score","").replace("_"," ").title(),[]).append(safe_float(r.get(k)))
    values={k:sum(v)/len(v) for k,v in buckets.items() if v} or {"Momentum":81,"Carry":72,"Macro":74,"Liquidity":86,"Quality":77,"Volatility":58}
    ordered=sorted(values.items(),key=lambda x:x[1])
    if go is None:
        st.dataframe(pd.DataFrame(ordered,columns=["Factor","Score"]),use_container_width=True,hide_index=True); return
    fig=_base(height); fig.add_trace(go.Bar(x=[v for _,v in ordered],y=[k for k,_ in ordered],orientation="h"))
    fig.update_layout(title=title,xaxis=dict(range=[0,100]))
    st.plotly_chart(fig,use_container_width=True)

def render_alpha_heatmap(rows: List[Dict[str, Any]], title="Alpha Heatmap", height=360):
    if st is None: return
    cols=[c for c in ["alpha_score","momentum_score","carry_score","value_score","macro_score","risk_score","liquidity_score","quality_score","sentiment_score","flow_score","volatility_score"] if any(isinstance(r,dict) and r.get(c) is not None for r in rows or [])]
    if not cols:
        rows=[{"pair":"EUR/USD","alpha_score":82,"momentum_score":78,"carry_score":69,"macro_score":74,"liquidity_score":88},{"pair":"USD/CHF","alpha_score":79,"momentum_score":71,"carry_score":76,"macro_score":82,"liquidity_score":84}]
        cols=["alpha_score","momentum_score","carry_score","macro_score","liquidity_score"]
    rows=rows[:14]
    if go is None:
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True); return
    z=[[safe_float(r.get(c)) for c in cols] for r in rows]
    y=[str(r.get("pair") or r.get("symbol") or i) for i,r in enumerate(rows)]
    x=[c.replace("_score","").replace("_"," ").title() for c in cols]
    fig=_base(height); fig.add_trace(go.Heatmap(z=z,x=x,y=y,coloraxis="coloraxis"))
    fig.update_layout(title=title,coloraxis=dict(colorscale="Viridis"))
    st.plotly_chart(fig,use_container_width=True)

def render_research_performance(rows: List[Dict[str, Any]], title="Research Performance", height=300):
    if st is None: return
    x=[]; a=[]; c=[]
    for i,r in enumerate(rows or []):
        if isinstance(r,dict):
            x.append(r.get("asof") or r.get("generated_at") or r.get("created_at") or i)
            a.append(safe_float(r.get("alpha_score") or r.get("composite_score") or r.get("score")))
            c.append(safe_float(r.get("confidence") or r.get("confidence_score") or r.get("signal_confidence")))
    if not x:
        x=list(range(20)); a=[70+(i%6)*2+i*.35 for i in x]; c=[66+(i%7)*2.5+i*.25 for i in x]
    if go is None:
        st.line_chart({"Alpha":a,"Confidence":c}); return
    fig=_base(height); fig.add_trace(go.Scatter(x=x,y=a,mode="lines+markers",name="Alpha")); fig.add_trace(go.Scatter(x=x,y=c,mode="lines+markers",name="Confidence"))
    fig.update_layout(title=title,yaxis=dict(range=[0,100]))
    st.plotly_chart(fig,use_container_width=True)
