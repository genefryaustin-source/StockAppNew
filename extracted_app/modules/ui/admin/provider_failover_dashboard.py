"""
ui/admin/provider_failover_dashboard.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.market_data.provider_router import (
    get_provider_router,
)


def render_provider_failover_dashboard():
    st.header(
        "Provider Failover Dashboard"
    )

    router = get_provider_router()

    providers = router.all_providers()

    if not providers:
        st.info(
            "No providers available."
        )
        return

    rows = []

    degraded = []
    unavailable = []

    for provider in providers:

        available = router.is_available(
            provider.provider
        )

        status = "AVAILABLE"

        if not available:
            status = "UNAVAILABLE"
            unavailable.append(
                provider.provider
            )

        elif provider.health_score < 60:
            status = "DEGRADED"
            degraded.append(
                provider.provider
            )

        rows.append({
            "provider": provider.provider,
            "status": status,
            "enabled": provider.enabled,
            "health_score": provider.health_score,
            "cooldown_until": provider.cooldown_until,
            "failure_count": provider.failure_count,
            "rate_limit_count": provider.rate_limit_count,
        })

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "Providers",
            len(rows),
        )

    with c2:
        st.metric(
            "Degraded",
            len(degraded),
        )

    with c3:
        st.metric(
            "Unavailable",
            len(unavailable),
        )

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader(
        "Current Failover Order"
    )

    ranked = router.get_ranked_providers()

    failover_rows = []

    for idx, provider in enumerate(
        ranked,
        start=1,
    ):
        failover_rows.append({
            "priority": idx,
            "provider": provider.provider,
            "health_score": provider.health_score,
        })

    st.dataframe(
        pd.DataFrame(failover_rows),
        use_container_width=True,
        hide_index=True,
    )