"""
ui/admin/rate_limit_dashboard.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.market_data.adaptive_rate_limit_manager import (
    get_rate_limit_manager,
)


def render_rate_limit_dashboard():
    st.header(
        "Adaptive Rate Limit Dashboard"
    )

    manager = get_rate_limit_manager()

    rows = manager.rows()

    if not rows:
        st.info(
            "No provider rate limit data."
        )
        return

    df = pd.DataFrame(rows)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )

    st.subheader(
        "Rate Limit Summary"
    )

    total_rate_limits = int(
        df["rate_limit_count"].sum()
    )

    providers = len(df)

    cooldowns = int(
        df["cooldown_until"]
        .notna()
        .sum()
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "Providers",
            providers,
        )

    with c2:
        st.metric(
            "Rate Limits",
            total_rate_limits,
        )

    with c3:
        st.metric(
            "Cooldowns",
            cooldowns,
        )