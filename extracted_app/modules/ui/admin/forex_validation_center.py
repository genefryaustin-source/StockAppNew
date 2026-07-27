"""
ui/admin/forex_validation_center.py

Administrative validation center for the Forex subsystem.
"""

from __future__ import annotations

try:
    import streamlit as st
    import pandas as pd
except Exception:
    st=None
    pd=None

from modules.forex.forex_system_validation_suite import run_forex_system_validation_suite
from modules.forex.forex_end_to_end_test_harness import run_forex_end_to_end_test_harness
from modules.forex.forex_production_readiness_suite import run_forex_production_readiness_suite


class ForexValidationCenter:

    def __init__(self, db=None):
        self.db=db

    def render(self):
        if st is None:
            return {"status":"streamlit_unavailable"}

        st.title("🧪 Forex Validation Center")

        workspace=st.radio(
            "Validation Workspace",
            ["System Validation","End-to-End","Production Readiness"],
            horizontal=True,
        )

        if workspace=="System Validation":
            if st.button("Run System Validation",use_container_width=True):
                report=run_forex_system_validation_suite(db=self.db)
                st.metric("Passed",report["passed"])
                st.metric("Failed",report["failed"])
                st.code(report["text_report"])
                st.dataframe(pd.DataFrame(report["results"]),use_container_width=True,hide_index=True)

        elif workspace=="End-to-End":
            if st.button("Run End-to-End Harness",use_container_width=True):
                report=run_forex_end_to_end_test_harness(db=self.db)
                st.metric("Passed",report["passed"])
                st.metric("Failed",report["failed"])
                st.code(report["text_report"])
                st.dataframe(pd.DataFrame(report["results"]),use_container_width=True,hide_index=True)

        else:
            if st.button("Run Production Readiness",use_container_width=True):
                report=run_forex_production_readiness_suite(db=self.db)
                st.metric("Overall Score",f"{report['overall_score']}%")
                st.metric("Passing Suites",report["passing_suites"])
                st.metric("Failing Suites",report["failing_suites"])
                st.code(report["text_report"])
                st.dataframe(pd.DataFrame(report["suites"]),use_container_width=True,hide_index=True)

_INSTANCE=None

def get_forex_validation_center(db=None):
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE=ForexValidationCenter(db=db)
    return _INSTANCE

def render_forex_validation_center(db=None):
    return get_forex_validation_center(db=db).render()
