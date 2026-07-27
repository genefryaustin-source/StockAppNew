
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    import streamlit as st
except Exception:
    st = None

from modules.forex.ui.forex_ui_theme import inject_forex_ui_theme
from modules.forex.ui.forex_ui_layout import panel, render_section_header
from modules.forex.ui.forex_factor_summary import extract_factor_rows, factor_commentary, FACTOR_KEYS
from modules.forex.ui.forex_factor_cards import render_factor_kpi_ribbon
from modules.forex.ui.forex_factor_charts import (
    render_factor_heatmap,
    render_factor_bar_stack,
    render_factor_radar,
    render_factor_correlation,
    render_factor_stability,
)
from modules.forex.ui.forex_factor_tables import (
    render_factor_ranking_table,
    render_top_contributors_table,
    render_factor_detail_table,
)

def render_forex_factor_models_workspace(payload: Optional[Dict[str, Any]] = None, *, db=None) -> Dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    rows = extract_factor_rows(payload)

    if st is None:
        return {"status": "READY", "rows": rows}

    inject_forex_ui_theme(st)
    render_section_header(
        "Factor Models Workstation",
        kicker="Institutional Factors",
        meta=datetime.now(timezone.utc).strftime("%H:%M:%S UTC"),
    )

    render_factor_kpi_ribbon(rows)

    with panel("Factor Heatmap", kicker="Cross-Pair Factor Matrix"):
        render_factor_heatmap(rows)

    left, right = st.columns([1.25, 1])

    with left:
        with panel("Factor Rankings", kicker="Composite"):
            render_factor_ranking_table(rows)

        with panel("Top Factor Contributors", kicker="Dominant Drivers"):
            render_top_contributors_table(rows)

        with panel("Factor Commentary", kicker="AI Narrative"):
            st.markdown(factor_commentary(rows))

    with right:
        with panel("Aggregate Factor Scores", kicker="Averages"):
            render_factor_bar_stack(rows)

        with panel("Factor Radar", kicker="Model Shape"):
            render_factor_radar(rows)

        with panel("Model Stability", kicker="Drift / Dispersion"):
            render_factor_stability(rows)

    with panel("Factor Correlation Matrix", kicker="Factor Relationships"):
        render_factor_correlation(rows)

    detail_tabs = st.tabs([f.title() for f in FACTOR_KEYS])
    for tab, factor in zip(detail_tabs, FACTOR_KEYS):
        with tab:
            render_section_header(f"{factor.title()} Dashboard", kicker="Factor Detail")
            render_factor_detail_table(rows, factor)

    return {"status": "READY", "rows": rows}
