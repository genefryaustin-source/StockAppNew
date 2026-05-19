import streamlit as st
import pandas as pd

from modules.analytics.strategy_service import list_discovered_strategies


def render_strategy_library(db, user):

    st.subheader("Strategy Library")

    tenant_id = user["tenant_id"]

    rows = list_discovered_strategies(db, tenant_id)

    if not rows:
        st.info("No saved strategies.")
        return

    df = pd.DataFrame([
        {
            "Name": r.name,
            "Factors": r.factors,
            "Return": r.return_pct,
            "Alpha": r.alpha,
            "Sharpe": r.sharpe,
            "Max Drawdown": r.max_drawdown,
            "Holdings": r.holdings,
        }
        for r in rows
    ])

    st.dataframe(df, use_container_width=True)