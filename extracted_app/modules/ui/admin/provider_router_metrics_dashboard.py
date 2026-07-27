"""
ui/admin/provider_router_metrics_dashboard.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.market_data.provider_router import (
    get_provider_router,
)


def render_provider_router_metrics_dashboard():
    st.header(
        "Provider Router Metrics"
    )

    router = get_provider_router()

    providers = router.all_providers()

    if not providers:
        st.info(
            "No providers registered."
        )
        return

    rows = []

    total_requests = 0
    total_success = 0
    total_failure = 0
    total_rate_limits = 0

    for provider in providers:

        requests = (
            provider.success_count
            + provider.failure_count
        )

        total_requests += requests
        total_success += provider.success_count
        total_failure += provider.failure_count
        total_rate_limits += provider.rate_limit_count

        success_rate = 0.0

        if requests > 0:
            success_rate = (
                provider.success_count
                / requests
            ) * 100

        rows.append({
            "provider": provider.provider,
            "enabled": provider.enabled,
            "health_score": round(
                provider.health_score,
                2,
            ),
            "requests": requests,
            "success_count": provider.success_count,
            "failure_count": provider.failure_count,
            "rate_limit_count": provider.rate_limit_count,
            "success_rate_pct": round(
                success_rate,
                2,
            ),
            "avg_latency_ms": round(
                provider.avg_latency_ms,
                2,
            ),
            "cooldown_until": provider.cooldown_until,
        })

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            "Requests",
            f"{total_requests:,}",
        )

    with c2:
        st.metric(
            "Success",
            f"{total_success:,}",
        )

    with c3:
        st.metric(
            "Failures",
            f"{total_failure:,}",
        )

    with c4:
        st.metric(
            "Rate Limits",
            f"{total_rate_limits:,}",
        )

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
    )