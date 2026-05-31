"""
ui/admin/provider_intelligence_dashboard.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.market_data.provider_intelligence_engine import (
    get_provider_intelligence_engine,
)


def render_provider_intelligence_dashboard():
    st.header("Provider Intelligence Dashboard")

    engine = get_provider_intelligence_engine()

    best = engine.best_provider()
    worst = engine.worst_provider()

    c1, c2 = st.columns(2)

    with c1:
        if best:
            st.metric(
                "Best Provider",
                best["provider"],
                f"{best['health_score']:.1f}",
            )

    with c2:
        if worst:
            st.metric(
                "Worst Provider",
                worst["provider"],
                f"{worst['health_score']:.1f}",
            )

    rows = engine.analyze_all_providers()

    if rows:
        st.subheader("Provider Intelligence")
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No provider intelligence available.")

    recommendations = engine.generate_routing_recommendations()

    st.subheader("Routing Recommendations")

    if recommendations:
        st.dataframe(
            pd.DataFrame(recommendations),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success("All providers currently appear healthy.")