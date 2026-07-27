"""
modules/execution/execution_operations_dashboard.py

Sprint 40.1

Institutional Execution Operations Center

Primary operational dashboard for the institutional execution
framework.

This dashboard provides real-time visibility into:

    • Execution Service
    • Event Store
    • Replay Engine
    • Projection Engine
    • Audit Engine
    • Compliance Engine
    • Archive Engine
    • Metrics Engine

Designed for Streamlit.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from modules.execution.execution_service import (
    get_execution_service,
)

from modules.execution.execution_event_metrics import (
    get_execution_event_metrics,
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

from modules.execution.execution_event_time_machine import (
    get_execution_event_time_machine,
)

from modules.execution.execution_event_projection import (
    get_execution_event_projection,
)

from modules.execution.execution_event_stream_validator import (
    get_execution_event_stream_validator,
)

from modules.execution.execution_event_replayer import (
    get_execution_event_replayer,
)


# ==============================================================================
# Helpers
# ==============================================================================


def _safe_call(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _metric_card(title, value, delta=None):
    st.metric(
        label=title,
        value=value,
        delta=delta,
    )


def _health(service):

    try:

        if hasattr(service, "health"):

            return service.health()

    except Exception:

        pass

    return {

        "healthy": True,

        "version": "-",

        "last_check": datetime.utcnow(),

    }


# ==============================================================================
# Dashboard
# ==============================================================================


def render_execution_operations_dashboard(
    db,
    portfolio_engine=None,
):

    st.title("⚙️ Institutional Execution Operations Center")

    st.caption(
        "Institutional Event-Sourced Execution Platform"
    )

    service = get_execution_service(
        db=db,
        portfolio_engine=portfolio_engine,
    )

    metrics = get_execution_event_metrics(
        db=db,
    )

    audit = get_execution_audit_engine(
        db=db,
    )

    compliance = get_execution_compliance_engine(
        db=db,
    )

    archive = get_execution_event_archive(
        db=db,
    )

    validator = get_execution_event_stream_validator(
        db=db,
    )

    projection = get_execution_event_projection(
        db=db,
    )

    replay = get_execution_event_replayer(
        db=db,
    )

    time_machine = get_execution_event_time_machine(
        db=db,
    )

    # ==========================================================
    # Metrics
    # ==========================================================

    agg = _safe_call(
        metrics.aggregate_metrics,
        {},
    )

    execution = agg.get(
        "execution_metrics",
        {},
    )

    orders = agg.get(
        "order_metrics",
        {},
    )

    latency = agg.get(
        "latency_metrics",
        {},
    )

    quality = agg.get(
        "quality_metrics",
        {},
    )

    archive_stats = _safe_call(
        archive.statistics,
        {},
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        _metric_card(

            "Executions",

            execution.get(
                "total_executions",
                0,
            ),

        )

        _metric_card(

            "Successful",

            execution.get(
                "successful",
                0,
            ),

        )

    with c2:

        _metric_card(

            "Orders",

            orders.get(
                "orders",
                0,
            ),

        )

        _metric_card(

            "Fill Rate",

            f"{orders.get('fill_rate',0):.2%}",

        )

    with c3:

        _metric_card(

            "Avg Fill",

            f"{latency.get('average',0):.2f}s",

        )

        _metric_card(

            "P95",

            f"{latency.get('p95',0):.2f}s",

        )

    with c4:

        _metric_card(

            "Archives",

            archive_stats.get(
                "archives",
                0,
            ),

        )

        _metric_card(

            "Archive Size",

            archive_stats.get(
                "storage_bytes",
                0,
            ),

        )

    st.divider()

    # ==========================================================
    # Health
    # ==========================================================

    st.subheader("System Health")

    health_rows = []

    services = {

        "Execution Service": service,

        "Projection Engine": projection,

        "Replay Engine": replay,

        "Validator": validator,

        "Time Machine": time_machine,

        "Audit": audit,

        "Compliance": compliance,

        "Archive": archive,

        "Metrics": metrics,

    }

    for name, svc in services.items():

        h = _health(svc)

        health_rows.append({

            "Component": name,

            "Healthy": h.get(
                "healthy",
                True,
            ),

            "Version": h.get(
                "version",
                "-",
            ),

            "Last Check": h.get(
                "last_check",
                "",
            ),

        })

    st.dataframe(

        pd.DataFrame(
            health_rows,
        ),

        use_container_width=True,

        hide_index=True,

    )

    st.divider()

    # ==========================================================
    # Tabs
    # ==========================================================

    tabs = st.tabs([

        "Metrics",

        "Replay",

        "Audit",

        "Compliance",

        "Archive",

        "Validation",

    ])

    # ==========================================================
    # Metrics
    # ==========================================================

    with tabs[0]:

        st.subheader(
            "Execution Metrics"
        )

        st.json(
            agg,
            expanded=False,
        )

    # ==========================================================
    # Replay
    # ==========================================================

    with tabs[1]:

        st.subheader(
            "Replay Controls"
        )

        replay_type = st.selectbox(

            "Replay Type",

            [

                "Execution",

                "Order",

                "Position",

                "Account",

                "Portfolio",

            ],

        )

        replay_id = st.text_input(
            "Identifier",
        )

        replay_time = st.text_input(

            "Timestamp (ISO8601)",

            "",

        )

        if st.button(
            "Replay",
            use_container_width=True,
        ):

            try:

                ts = datetime.fromisoformat(
                    replay_time
                )

                if replay_type == "Execution":

                    result = time_machine.execution_at(

                        execution_id=replay_id,

                        timestamp=ts,

                    )

                elif replay_type == "Order":

                    result = time_machine.order_at(

                        broker_order_id=replay_id,

                        timestamp=ts,

                    )

                elif replay_type == "Position":

                    result = time_machine.position_at(

                        position_id=replay_id,

                        timestamp=ts,

                    )

                elif replay_type == "Account":

                    result = time_machine.account_at(

                        account_id=replay_id,

                        timestamp=ts,

                    )

                else:

                    result = time_machine.portfolio_at(

                        portfolio_id=replay_id,

                        timestamp=ts,

                    )

                st.write(result)

            except Exception as exc:

                st.error(exc)

    # ==========================================================
    # Audit
    # ==========================================================

    with tabs[2]:

        st.subheader(
            "Audit"
        )

        entity = st.selectbox(

            "Entity",

            [

                "execution",

                "order",

                "position",

                "account",

                "portfolio",

            ],

        )

        entity_id = st.text_input(
            "Entity ID",
            key="audit",
        )

        if st.button(
            "Run Audit",
        ):

            try:

                report = audit.export_audit_report(

                    entity_type=entity,

                    entity_id=entity_id,

                )

                st.json(report)

            except Exception as exc:

                st.error(exc)

    # ==========================================================
    # Compliance
    # ==========================================================

    with tabs[3]:

        st.subheader(
            "Compliance"
        )

        entity = st.selectbox(

            "Compliance Target",

            [

                "Execution",

                "Order",

                "Position",

                "Account",

                "Portfolio",

            ],

        )

        entity_id = st.text_input(
            "Identifier",
            key="compliance",
        )

        if st.button(
            "Evaluate",
        ):

            try:

                if entity == "Execution":

                    result = compliance.evaluate_execution(

                        execution_id=entity_id,

                    )

                elif entity == "Order":

                    result = compliance.evaluate_order(

                        broker_order_id=entity_id,

                    )

                elif entity == "Position":

                    result = compliance.evaluate_position(

                        position_id=entity_id,

                    )

                elif entity == "Account":

                    result = compliance.evaluate_account(

                        account_id=entity_id,

                    )

                else:

                    result = compliance.evaluate_portfolio(

                        portfolio_id=entity_id,

                    )

                st.json(
                    result.to_dict(),
                )

            except Exception as exc:

                st.error(exc)

    # ==========================================================
    # Archive
    # ==========================================================

    with tabs[4]:

        st.subheader(
            "Archive"
        )

        st.json(
            archive_stats,
        )

        archive_id = st.text_input(
            "Archive ID",
        )

        c1, c2 = st.columns(2)

        with c1:

            if st.button(
                "Verify Archive",
                use_container_width=True,
            ):

                try:

                    st.json(

                        archive.verify_archive(

                            archive_id,

                        )

                    )

                except Exception as exc:

                    st.error(exc)

        with c2:

            if st.button(
                "Restore Archive",
                use_container_width=True,
            ):

                try:

                    restored = archive.restore(
                        archive_id,
                    )

                    st.success(
                        f"Restored {len(restored)} events."
                    )

                    st.dataframe(
                        pd.DataFrame(
                            restored,
                        ),
                        use_container_width=True,
                    )

                except Exception as exc:

                    st.error(exc)

    # ==========================================================
    # Validation
    # ==========================================================

    with tabs[5]:

        st.subheader(
            "Event Stream Validation"
        )

        execution_id = st.text_input(
            "Execution ID",
            key="validate",
        )

        if st.button(
            "Validate",
        ):

            try:

                result = validator.validate_execution(
                    execution_id,
                )

                if hasattr(result, "to_dict"):

                    st.json(
                        result.to_dict(),
                    )

                else:

                    st.write(result)

            except Exception as exc:

                st.error(exc)

    st.divider()

    st.caption(

        "Institutional Execution Framework • Sprint 40.1"

    )