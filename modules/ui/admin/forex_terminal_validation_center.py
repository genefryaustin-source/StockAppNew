
from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.forex.forex_terminal_validation_center import get_forex_terminal_validation_center


def render_forex_terminal_validation_center(db=None):
    st.title("Forex Terminal Validation Center")
    st.caption("Phase 9 hardened validation for the institutional Forex terminal.")

    execute_trade = st.checkbox("Submit 0.01 lot EUR/USD paper test order", value=False)
    run = st.button("Run Full Forex Validation", type="primary", use_container_width=True)

    if not run:
        st.info("Run validation after installing Phases 1–8.")
        return

    result = get_forex_terminal_validation_center(db=db).run_validation(execute_trade=execute_trade)

    summary = result.get("summary", {})
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Status", result.get("status"))
    c2.metric("Passed", summary.get("passed", 0))
    c3.metric("Failed", summary.get("failed", 0))
    c4.metric("Required Failed", summary.get("required_failed", 0))

    df = pd.DataFrame(result.get("results", []))
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)

    with st.expander("Validation Artifacts", expanded=False):
        st.json(result.get("artifacts", {}))


def render_admin_forex_terminal_validation(db=None):
    return render_forex_terminal_validation_center(db=db)
