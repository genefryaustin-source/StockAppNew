
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    import streamlit as st
    import pandas as pd
except Exception:
    st = None
    pd = None

from modules.forex.ui.forex_ui_theme import inject_forex_ui_theme
from modules.forex.ui.forex_ui_layout import panel, render_section_header
from modules.forex.ui.forex_ui_status import render_status_pill
from modules.forex.ui.forex_alpha_summary import extract_alpha_rows, alpha_commentary, top_alpha_table, safe_float
from modules.forex.ui.forex_alpha_cards import render_alpha_kpi_ribbon
from modules.forex.ui.forex_alpha_charts import (
    render_alpha_score_bar,
    render_alpha_confidence_scatter,
    render_alpha_heatmap,
    render_alpha_timeline,
    render_signal_mix,
)

def _table(rows, height=320):
    if st is None:
        return rows
    if pd is None:
        st.write(rows)
        return
    df = pd.DataFrame(rows if isinstance(rows, list) else [rows])
    if df.empty:
        st.info("No rows available.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True, height=height)

def render_forex_alpha_research_workspace(payload: Optional[Dict[str, Any]] = None, *, db=None) -> Dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    rows = extract_alpha_rows(payload)

    if st is None:
        return {"status": "READY", "rows": rows}

    inject_forex_ui_theme(st)
    render_section_header(
        "Alpha Research Workstation",
        kicker="Institutional Alpha",
        meta=datetime.now(timezone.utc).strftime("%H:%M:%S UTC"),
    )

    render_alpha_kpi_ribbon(rows)

    top = rows[0] if rows else {}
    with panel("Alpha Decision Banner", kicker="Top Opportunity", meta=str(top.get("status", "READY"))):
        c1, c2, c3, c4 = st.columns([1.25, 1, 1, 1])
        c1.markdown(f"## {top.get('signal', 'WATCH')} {top.get('pair', 'EUR/USD')}")
        c2.metric("Alpha", f"{safe_float(top.get('alpha_score')):.0f}")
        c3.metric("Confidence", f"{safe_float(top.get('confidence')):.0f}%")
        c4.metric("Risk/Reward", f"{safe_float(top.get('risk_reward')):.2f}")
        render_status_pill(top.get("status", "READY"), label=f"Grade {top.get('grade', 'A')}")

    left, right = st.columns([1.35, 1])

    with left:
        with panel("Institutional Alpha Ranking", kicker="Opportunities"):
            _table(top_alpha_table(rows), height=430)

        with panel("Alpha Narrative", kicker="AI Research Summary"):
            st.markdown(alpha_commentary(rows))

        with panel("Alpha Timeline", kicker="Model History"):
            render_alpha_timeline(rows)

    with right:
        with panel("Alpha Scores", kicker="Ranking"):
            render_alpha_score_bar(rows)

        with panel("Alpha vs Confidence", kicker="Conviction"):
            render_alpha_confidence_scatter(rows)

        with panel("Signal Mix", kicker="Direction"):
            render_signal_mix(rows)

    with panel("Alpha Opportunity Heatmap", kicker="Factor Confirmation"):
        render_alpha_heatmap(rows)

    with panel("Trade Level Review", kicker="Targets / Stops / Risk"):
        review = []
        for row in rows[:12]:
            review.append({
                "Pair": row.get("pair"),
                "Signal": row.get("signal"),
                "Entry": row.get("entry") or row.get("entry_price") or row.get("suggested_entry") or "-",
                "Target": row.get("target") or row.get("target_price") or row.get("suggested_target") or "-",
                "Stop": row.get("stop") or row.get("stop_price") or row.get("suggested_stop") or "-",
                "Risk Reward": row.get("risk_reward"),
                "Expected Return": row.get("expected_return"),
                "Status": row.get("status"),
            })
        _table(review, height=330)

    return {"status": "READY", "rows": rows}
