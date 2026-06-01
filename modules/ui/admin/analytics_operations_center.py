"""
ui/admin/analytics_operations_center.py
"""

from __future__ import annotations

import streamlit as st

from ui.admin.analytics_governor_dashboard import (
    render_analytics_governor_dashboard,
)

from ui.admin.analytics_scheduler_dashboard import (
    render_analytics_scheduler_dashboard,
)

from ui.admin.analytics_optimizer_dashboard import (
    render_analytics_optimizer_dashboard,
)


def render_analytics_operations_center():

    st.title(
        "Analytics Operations Center"
    )

    overview_tab, governor_tab, scheduler_tab, optimizer_tab = st.tabs([
        "Overview",
        "Governor",
        "Scheduler",
        "Optimizer",
    ])

    with overview_tab:

        st.subheader(
            "Analytics Control Plane"
        )

        st.markdown("""
### Analytics Components

- Intelligent Analytics Scheduler
- Universe Analytics Orchestrator
- Analytics Resource Governor
- Autonomous Analytics Optimizer

### Responsibilities

- Universe prioritization
- Resource governance
- Concurrency control
- Failure management
- Autonomous optimization
- Analytics orchestration
""")

    with governor_tab:

        render_analytics_governor_dashboard()

    with scheduler_tab:

        render_analytics_scheduler_dashboard()

    with optimizer_tab:

        render_analytics_optimizer_dashboard()