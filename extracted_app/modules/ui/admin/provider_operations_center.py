"""
ui/admin/provider_operations_center.py
"""

from __future__ import annotations

import streamlit as st

from ui.admin.provider_health_dashboard_page import (
    render_provider_health_dashboard_page,
)

from ui.admin.provider_cache_dashboard import (
    render_provider_cache_dashboard,
)

from ui.admin.rate_limit_dashboard import (
    render_rate_limit_dashboard,
)

from ui.admin.provider_router_control_center import (
    render_provider_router_control_center,
)


def render_provider_operations_center(
    db,
    user=None,
):
    st.title(
        "Provider Operations Center"
    )

    st.caption(
        "Provider health, routing, cache, and rate-limit management."
    )

    overview_tab, health_tab, cache_tab, rate_limit_tab, router_tab = st.tabs([
        "Overview",
        "Provider Health",
        "Provider Cache",
        "Rate Limits",
        "Router Control",
    ])

    # ---------------------------------------------------------
    # OVERVIEW
    # ---------------------------------------------------------

    with overview_tab:

        st.subheader(
            "Provider Operations Overview"
        )

        c1, c2, c3 = st.columns(3)

        with c1:
            st.info(
                "Provider Health Monitoring"
            )

        with c2:
            st.info(
                "Adaptive Rate Limiting"
            )

        with c3:
            st.info(
                "Provider Routing Control"
            )

        st.divider()

        st.markdown("""
### Capabilities

- Provider Health Monitoring
- Adaptive Rate Limit Tracking
- Provider Cache Visibility
- Provider Routing Control
- Health Score Management
- Provider Enable / Disable
- Cooldown Tracking
- Cache Maintenance
- Operational Diagnostics
""")

    # ---------------------------------------------------------
    # HEALTH
    # ---------------------------------------------------------

    with health_tab:

        render_provider_health_dashboard_page(
            db=db,
            user=user,
        )

    # ---------------------------------------------------------
    # CACHE
    # ---------------------------------------------------------

    with cache_tab:

        render_provider_cache_dashboard(
            db=db,
        )

    # ---------------------------------------------------------
    # RATE LIMITS
    # ---------------------------------------------------------

    with rate_limit_tab:

        render_rate_limit_dashboard()

    # ---------------------------------------------------------
    # ROUTER CONTROL
    # ---------------------------------------------------------

    with router_tab:

        render_provider_router_control_center()