"""
modules/forex/forex_command_center_dashboard.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.forex.forex_command_center_engine import (
    get_forex_command_center_engine,
)

_ENGINE=get_forex_command_center_engine()

def render_forex_command_center():
    st.title("Forex Command Center")

    if st.button("Refresh",use_container_width=True):
        st.rerun()

    data=_ENGINE.build()

    summary=data.get("summary",{})
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Macro Regime",summary.get("macro_regime","-"))
    c2.metric("Macro Score",summary.get("macro_score","-"))
    c3.metric("Strongest",(summary.get("strongest_currency") or {}).get("currency","-"))
    c4.metric("Weakest",(summary.get("weakest_currency") or {}).get("currency","-"))

    tabs=st.tabs([
        "Currency Strength",
        "Top Opportunities",
        "Institutional Flow",
        "Carry Trades",
        "Central Banks",
        "Sentiment",
    ])

    with tabs[0]:
        st.dataframe(
            pd.DataFrame(data.get("currency_strength",[])),
            use_container_width=True,
            hide_index=True,
        )

    with tabs[1]:
        st.dataframe(
            pd.DataFrame(data.get("top_opportunities",[])),
            use_container_width=True,
            hide_index=True,
        )

    with tabs[2]:
        st.dataframe(
            pd.DataFrame(data.get("institutional_flow",[])),
            use_container_width=True,
            hide_index=True,
        )

    with tabs[3]:
        st.dataframe(
            pd.DataFrame(data.get("carry_trades",[])),
            use_container_width=True,
            hide_index=True,
        )

    with tabs[4]:
        st.dataframe(
            pd.DataFrame(data.get("central_banks",[])),
            use_container_width=True,
            hide_index=True,
        )

    with tabs[5]:
        st.dataframe(
            pd.DataFrame(data.get("sentiment",[])),
            use_container_width=True,
            hide_index=True,
        )
