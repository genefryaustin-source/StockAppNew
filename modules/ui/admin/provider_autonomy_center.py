"""
ui/admin/provider_autonomy_center.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.market_data.autonomous_provider_optimizer import (
    get_autonomous_provider_optimizer,
)


def render_provider_autonomy_center():
    st.header("Provider Autonomy Center")

    optimizer = get_autonomous_provider_optimizer()

    c1, c2 = st.columns(2)

    with c1:
        dry_run = st.checkbox(
            "Dry Run",
            value=True,
            key="provider_optimizer_dry_run",
        )

    with c2:
        run = st.button(
            "Run Provider Optimizer",
            type="primary",
            key="run_provider_optimizer",
        )

    if run:
        result = optimizer.optimize(
            dry_run=dry_run,
        )

        st.success("Provider optimizer completed.")

        st.json(result)

    st.subheader("Current Optimization Plan")

    plan = optimizer.build_optimization_plan()

    actions = plan.get("actions", [])

    if actions:
        st.dataframe(
            pd.DataFrame(actions),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success("No provider optimization actions required.")