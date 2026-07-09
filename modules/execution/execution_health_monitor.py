"""
modules/execution/execution_health_monitor.py

Sprint 40.6

Institutional Execution Health Monitor

The centralized monitoring console for the institutional execution
framework.

This module continuously monitors every execution subsystem and
provides health, readiness, capability, and operational status.

Designed for Streamlit.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from modules.execution.execution_service import (
    get_execution_service,
)

from modules.execution.execution_event_replayer import (
    get_execution_event_replayer,
)

from modules.execution.execution_event_projection import (
    get_execution_event_projection,
)

from modules.execution.execution_event_stream_validator import (
    get_execution_event_stream_validator,
)

from modules.execution.execution_event_time_machine import (
    get_execution_event_time_machine,
)

from modules.execution.execution_audit_engine import (
    get_execution_audit_engine,
)

from modules.execution.execution_compliance_engine import (
    get_execution_compliance_engine,
)

from modules.execution.execution_event_archive import (
    get_execution_event_archive,
)

from modules.execution.execution_event_metrics import (
    get_execution_event_metrics,
)

from modules.execution.execution_event_explorer import (
    get_execution_event_explorer,
)


# ==============================================================================
# Helpers
# ==============================================================================


def _utcnow() -> str:
    return datetime.utcnow().replace(
        microsecond=0
    ).isoformat()


def _service_health(
    name: str,
    service: Any,
) -> Dict[str, Any]:

    try:

        if hasattr(service, "health"):

            health = service.health()

            if isinstance(
                health,
                dict,
            ):

                health.setdefault(
                    "service",
                    name,
                )

                health.setdefault(
                    "healthy",
                    True,
                )

                health.setdefault(
                    "last_check",
                    _utcnow(),
                )

                return health

    except Exception as exc:

        return {

            "service": name,

            "healthy": False,

            "status": "ERROR",

            "version": "-",

            "last_check": _utcnow(),

            "message": str(exc),

        }

    return {

        "service": name,

        "healthy": True,

        "status": "OK",

        "version": "-",

        "last_check": _utcnow(),

        "message": "Health method not implemented.",

    }


# ==============================================================================
# Dashboard
# ==============================================================================


def render_execution_health_monitor(
    db,
    portfolio_engine=None,
):

    st.title(
        "🩺 Institutional Execution Health Monitor"
    )

    st.caption(
        "Execution Infrastructure Monitoring"
    )

    # ------------------------------------------------------------------
    # Services
    # ------------------------------------------------------------------

    services = {

        "Execution Service":

            get_execution_service(

                db=db,

                portfolio_engine=portfolio_engine,

            ),

        "Replay Engine":

            get_execution_event_replayer(
                db=db,
            ),

        "Projection Engine":

            get_execution_event_projection(
                db=db,
            ),

        "Validator":

            get_execution_event_stream_validator(
                db=db,
            ),

        "Time Machine":

            get_execution_event_time_machine(
                db=db,
            ),

        "Audit Engine":

            get_execution_audit_engine(
                db=db,
            ),

        "Compliance Engine":

            get_execution_compliance_engine(
                db=db,
            ),

        "Archive Engine":

            get_execution_event_archive(
                db=db,
            ),

        "Metrics Engine":

            get_execution_event_metrics(
                db=db,
            ),

        "Event Explorer":

            get_execution_event_explorer(
                db=db,
            ),

    }

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    refresh = st.button(
        "Refresh Health",
        use_container_width=True,
    )

    if refresh:
        st.rerun()

    # ------------------------------------------------------------------
    # Health Collection
    # ------------------------------------------------------------------

    rows: List[Dict[str, Any]] = []

    healthy = 0

    unhealthy = 0

    warnings = 0

    for name, svc in services.items():

        health = _service_health(
            name,
            svc,
        )

        rows.append(health)

        if health.get(
            "healthy",
            False,
        ):
            healthy += 1

            if health.get(
                "status",
                "OK",
            ) != "OK":
                warnings += 1

        else:
            unhealthy += 1

    # ------------------------------------------------------------------
    # KPI Cards
    # ------------------------------------------------------------------

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.metric(
            "Services",
            len(rows),
        )

    with c2:

        st.metric(
            "Healthy",
            healthy,
        )

    with c3:

        st.metric(
            "Warnings",
            warnings,
        )

    with c4:

        st.metric(
            "Failures",
            unhealthy,
        )

    st.divider()

    # ------------------------------------------------------------------
    # Workspace
    # ------------------------------------------------------------------

    workspace = st.radio(

        "Workspace",

        [

            "Overview",

            "Services",

            "Capabilities",

            "Diagnostics",

            "Statistics",

            "Raw",

        ],

        horizontal=True,

    )

    # ------------------------------------------------------------------
    # Overview
    # ------------------------------------------------------------------

    if workspace == "Overview":

        st.subheader(
            "Execution Infrastructure Status"
        )

        overview = pd.DataFrame(rows)

        st.dataframe(

            overview,

            use_container_width=True,

            hide_index=True,

        )

    # ------------------------------------------------------------------
    # Services
    # ------------------------------------------------------------------

    elif workspace == "Services":

        st.subheader(
            "Service Details"
        )

        service_names = list(
            services.keys()
        )

        selected = st.selectbox(

            "Service",

            service_names,

        )

        health = _service_health(

            selected,

            services[selected],

        )

        st.json(
            health,
        )

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    elif workspace == "Capabilities":

        st.subheader(
            "Registered Capabilities"
        )

        capabilities = []

        for name, svc in services.items():

            health = _service_health(
                name,
                svc,
            )

            caps = health.get(
                "capabilities",
                [],
            )

            if not caps:

                capabilities.append({

                    "Service": name,

                    "Capability": "-",

                })

            else:

                for cap in caps:

                    capabilities.append({

                        "Service": name,

                        "Capability": cap,

                    })

        st.dataframe(

            pd.DataFrame(
                capabilities,
            ),

            use_container_width=True,

            hide_index=True,

        )

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    elif workspace == "Diagnostics":

        st.subheader(
            "Diagnostics"
        )

        diagnostics = []

        for row in rows:

            diagnostics.append({

                "Service":

                    row.get(
                        "service",
                    ),

                "Healthy":

                    row.get(
                        "healthy",
                    ),

                "Status":

                    row.get(
                        "status",
                        "OK",
                    ),

                "Version":

                    row.get(
                        "version",
                        "-",
                    ),

                "Last Check":

                    row.get(
                        "last_check",
                    ),

                "Message":

                    row.get(
                        "message",
                        "",
                    ),

            })

        st.dataframe(

            pd.DataFrame(
                diagnostics,
            ),

            use_container_width=True,

            hide_index=True,

        )

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    elif workspace == "Statistics":

        st.subheader(
            "Operational Statistics"
        )

        metrics = get_execution_event_metrics(
            db=db,
        )

        stats = metrics.aggregate_metrics()

        st.json(
            stats,
            expanded=False,
        )

    # ------------------------------------------------------------------
    # Raw
    # ------------------------------------------------------------------

    elif workspace == "Raw":

        st.subheader(
            "Raw Health Payload"
        )

        payload = {

            row["service"]: row

            for row in rows

        }

        st.json(
            payload,
            expanded=False,
        )

    st.divider()

    st.caption(

        f"Execution Health Monitor • "
        f"Sprint 40.6 • "
        f"Generated {_utcnow()}"

    )