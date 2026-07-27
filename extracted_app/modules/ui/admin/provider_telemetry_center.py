"""
ui/admin/provider_telemetry_center.py
"""

from __future__ import annotations

import pandas as pd
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

from ui.admin.provider_router_metrics_dashboard import (
    render_provider_router_metrics_dashboard,
)

from ui.admin.provider_failover_dashboard import (
    render_provider_failover_dashboard,
)

from ui.admin.provider_router_control_center import (
    render_provider_router_control_center,
)


def render_provider_telemetry_center(
    db,
    user=None,
):
    st.title(
        "Provider Telemetry Center"
    )

    overview_tab, metrics_tab, failover_tab, health_tab, cache_tab, limits_tab, control_tab = st.tabs([
        "Overview",
        "Metrics",
        "Failover",
        "Health",
        "Cache",
        "Rate Limits",
        "Control",
    ])

    with overview_tab:

        st.subheader(
            "Provider Operations"
        )

        st.markdown("""
### Telemetry Modules

- Provider Metrics
- Provider Health
- Provider Failover
- Adaptive Rate Limits
- Provider Cache
- Router Controls
- Cooldown Tracking
- Health Score Monitoring
""")

    with metrics_tab:

        render_provider_router_metrics_dashboard()

    with failover_tab:

        render_provider_failover_dashboard()

    with health_tab:

        render_provider_health_dashboard_page(
            db=db,
            user=user,
        )

    with cache_tab:

        render_provider_cache_dashboard(
            db=db,
        )

    with limits_tab:

        render_rate_limit_dashboard()

    with control_tab:

        render_provider_router_control_center()