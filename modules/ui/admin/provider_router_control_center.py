"""
ui/admin/provider_router_control_center.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.market_data.provider_router import (
    get_provider_router,
)


def render_provider_router_control_center():
    st.header(
        "Provider Router Control Center"
    )

    router = get_provider_router()

    providers = router.all_providers()

    if not providers:
        st.info(
            "No providers registered."
        )
        return

    rows = []

    for provider in providers:

        rows.append({
            "provider": provider.provider,
            "enabled": provider.enabled,
            "health_score": provider.health_score,
            "success_count": provider.success_count,
            "failure_count": provider.failure_count,
            "rate_limit_count": provider.rate_limit_count,
            "avg_latency_ms": provider.avg_latency_ms,
            "cooldown_until": provider.cooldown_until,
        })

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    st.subheader(
        "Provider Controls"
    )

    for provider in providers:

        c1, c2, c3, c4 = st.columns(
            [3, 1, 1, 1]
        )

        with c1:
            st.write(
                provider.provider
            )

        with c2:

            if st.button(
                "Enable",
                key=f"enable_{provider.provider}",
            ):
                router.enable_provider(
                    provider.provider
                )
                st.rerun()

        with c3:

            if st.button(
                "Disable",
                key=f"disable_{provider.provider}",
            ):
                router.disable_provider(
                    provider.provider
                )
                st.rerun()

        with c4:

            if st.button(
                "Reset",
                key=f"reset_{provider.provider}",
            ):
                router.reset_health(
                    provider.provider
                )
                st.rerun()