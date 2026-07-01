
from __future__ import annotations
from typing import Any, Dict, List
try:
    import streamlit as st
    import pandas as pd
except Exception:
    st = None
    pd = None
from modules.forex.ui.forex_factor_summary import FACTOR_KEYS, factor_score, top_contributors

def _table(rows: Any, height: int = 320):
    if st is None:
        return rows
    if pd is None:
        st.write(rows)
        return
    data = pd.DataFrame(rows if isinstance(rows, list) else [rows])
    if data.empty:
        st.info("No rows available.")
        return
    st.dataframe(data, use_container_width=True, hide_index=True, height=height)

def render_factor_ranking_table(rows: List[Dict[str, Any]], height: int = 420):
    ranked = []
    for idx, row in enumerate(rows, start=1):
        avg = sum(factor_score(row, f) for f in FACTOR_KEYS) / len(FACTOR_KEYS)
        ranked.append({
            "Rank": idx,
            "Pair": row.get("pair") or row.get("symbol") or "FX",
            "Composite": round(avg, 2),
            **{f.title(): round(factor_score(row, f), 2) for f in FACTOR_KEYS},
            "Status": "READY" if avg >= 70 else "WATCH",
        })
    ranked.sort(key=lambda r: r["Composite"], reverse=True)
    for i, row in enumerate(ranked, start=1):
        row["Rank"] = i
    _table(ranked, height=height)

def render_top_contributors_table(rows: List[Dict[str, Any]], height: int = 320):
    _table(top_contributors(rows), height=height)

def render_factor_detail_table(rows: List[Dict[str, Any]], factor: str, height: int = 260):
    data = []
    for row in rows:
        score = factor_score(row, factor)
        data.append({
            "Pair": row.get("pair") or row.get("symbol") or "FX",
            "Factor": factor.title(),
            "Score": round(score, 2),
            "Interpretation": "Strong" if score >= 75 else "Neutral" if score >= 60 else "Weak",
        })
    data.sort(key=lambda r: r["Score"], reverse=True)
    _table(data, height=height)
