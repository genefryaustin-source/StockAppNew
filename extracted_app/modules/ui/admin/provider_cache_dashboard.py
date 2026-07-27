"""
ui/admin/provider_cache_dashboard.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.market_data.provider_cache_manager import (
    get_provider_cache_status,
    clear_expired_provider_cache,
)


def render_provider_cache_dashboard(
    db,
):
    st.header(
        "Provider Cache Dashboard"
    )

    c1, c2 = st.columns(2)

    with c1:

        if st.button(
            "Refresh Cache Status",
            key="provider_cache_refresh",
        ):
            st.rerun()

    with c2:

        if st.button(
            "Clear Expired Cache",
            key="provider_cache_cleanup",
        ):
            removed = clear_expired_provider_cache(
                db
            )

            st.success(
                f"Removed {removed:,} expired cache records."
            )

            st.rerun()

    rows = get_provider_cache_status(db)

    if not rows:
        st.info(
            "No provider cache records found."
        )
        return

    df = pd.DataFrame(rows)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )

    st.subheader(
        "Cache Summary"
    )

    total_records = int(
        df["records"].sum()
    )

    providers = int(
        df["provider"].nunique()
    )

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "Cache Records",
            f"{total_records:,}",
        )

    with col2:
        st.metric(
            "Providers",
            providers,
        )