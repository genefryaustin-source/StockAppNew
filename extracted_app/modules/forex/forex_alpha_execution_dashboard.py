"""
===============================================================================
Sprint 25 - Phase 1
Alpha Execution Dashboard

File:
    modules/forex/forex_alpha_execution_dashboard.py

Purpose:
    Visual dashboard for the Alpha Execution Profiler.
===============================================================================
"""

from __future__ import annotations

from datetime import datetime, timezone

try:
    import streamlit as st
except Exception:
    st = None

from modules.forex.forex_alpha_execution_profiler import (
    get_forex_alpha_execution_profiler,
)


class ForexAlphaExecutionDashboard:

    def __init__(self, db=None):
        self.db = db
        self.profiler = get_forex_alpha_execution_profiler()

    def render(self):

        payload = self.profiler.export()

        if st is None:
            return payload

        st.subheader("⚡ Alpha Execution Audit")

        metrics = payload["metrics"]

        c1, c2, c3, c4, c5, c6 = st.columns(6)

        c1.metric(
            "Executions",
            metrics["executions"],
        )

        c2.metric(
            "Functions",
            metrics["unique_functions"],
        )

        c3.metric(
            "Callers",
            metrics["unique_callers"],
        )

        c4.metric(
            "Duplicates",
            metrics["duplicates"],
        )

        c5.metric(
            "Failures",
            metrics["failures"],
        )

        c6.metric(
            "Elapsed (ms)",
            metrics["elapsed_ms"],
        )

        tabs = st.tabs([
            "Execution Summary",
            "Duplicate Calls",
            "Call Graph",
            "Slowest Functions",
            "Raw Records",
        ])

        with tabs[0]:

            st.caption("Execution Summary")

            st.dataframe(
                payload["summary"],
                use_container_width=True,
                hide_index=True,
            )

        with tabs[1]:

            st.caption("Duplicate Executions")

            st.dataframe(
                payload["duplicates"],
                use_container_width=True,
                hide_index=True,
            )

        with tabs[2]:

            st.caption("Call Graph")

            st.json(
                payload["call_graph"]
            )

        with tabs[3]:

            st.caption("Slowest Executions")

            st.dataframe(
                payload["slowest"],
                use_container_width=True,
                hide_index=True,
            )

        with tabs[4]:

            st.caption("Execution History")

            st.dataframe(
                payload["records"],
                use_container_width=True,
                hide_index=True,
            )

        st.divider()

        col1, col2 = st.columns(2)

        with col1:

            if st.button(
                "Reset Profiler",
                use_container_width=True,
            ):
                self.profiler.reset()
                st.success("Profiler reset.")
                st.rerun()

        with col2:

            st.download_button(
                "Export JSON",
                data=str(payload),
                file_name=f"alpha_execution_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True,
            )

        return payload


_INSTANCE = None


def get_forex_alpha_execution_dashboard(db=None):

    global _INSTANCE

    if (
        _INSTANCE is None
        or (
            db is not None
            and getattr(_INSTANCE, "db", None) is None
        )
    ):
        _INSTANCE = ForexAlphaExecutionDashboard(db=db)

    return _INSTANCE


def render_forex_alpha_execution_dashboard(
    db=None,
    **kwargs,
):
    return get_forex_alpha_execution_dashboard(
        db=db,
    ).render()