# ui/admin/provider_operations_dashboard.py

from __future__ import annotations

from typing import Any, Optional

import streamlit as st
from sqlalchemy.orm import Session

from modules.data.provider_health_service import (
    initialize_provider_health,
    provider_health_dataframe,
    provider_health_metrics,
)


def _fmt_number(value: Any) -> str:
    try:
        return f"{int(value or 0):,}"
    except Exception:
        return "0"


def _fmt_pct(value: Any) -> str:
    try:
        return f"{float(value or 0):.2f}%"
    except Exception:
        return "0.00%"


def render_provider_operations_dashboard(
    db: Session,
    user: Optional[dict] = None,
) -> None:
    st.markdown("## Data Provider Operations Center")

    try:
        initialize_provider_health(db)
    except Exception as exc:
        st.error(f"Provider health initialization failed: {exc}")
        return

    metrics = provider_health_metrics(db)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Success Rate", _fmt_pct(metrics.get("success_rate")))
    c2.metric("Avg Health", _fmt_pct(metrics.get("avg_health_score")))
    c3.metric(
        "Providers Online",
        f"{_fmt_number(metrics.get('available_providers'))}/{_fmt_number(metrics.get('providers'))}",
    )
    c4.metric("Avg Latency", f"{float(metrics.get('avg_latency_ms') or 0):.0f} ms")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Successes", _fmt_number(metrics.get("successes")))
    c6.metric("Failures", _fmt_number(metrics.get("failures")))
    c7.metric("Rate Limits", _fmt_number(metrics.get("rate_limits")))
    c8.metric("Status", "Live")

    st.divider()

    st.markdown("### Provider Health Table")
    df = provider_health_dataframe(db)

    if df.empty:
        st.info("No provider health rows found.")
    else:
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            height=420,
        )

    st.divider()

    if st.button("Seed / Repair Provider Health Rows", type="primary"):
        initialize_provider_health(db)
        st.success("Provider health rows seeded/repaired.")
        st.rerun()
