"""
modules/execution/execution_audit_dashboard.py

Sprint 40.4

Institutional Execution Audit Dashboard

Provides a complete audit workstation for investigating the
immutable execution event stream.

This dashboard is UI-only and delegates all business logic to the
execution subsystem services.
"""

from __future__ import annotations

import json
from datetime import datetime

import pandas as pd
import streamlit as st

from modules.execution.execution_event_explorer import (
    get_execution_event_explorer,
)
from modules.execution.execution_audit_engine import (
    get_execution_audit_engine,
)
from modules.execution.execution_event_time_machine import (
    get_execution_event_time_machine,
)
from modules.execution.execution_event_stream_validator import (
    get_execution_event_stream_validator,
)
from modules.execution.execution_compliance_engine import (
    get_execution_compliance_engine,
)
from modules.execution.execution_event_metrics import (
    get_execution_event_metrics,
)


# ==============================================================================
# Helpers
# ==============================================================================


def _safe_call(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _to_json(obj):
    if obj is None:
        return {}

    if hasattr(obj, "to_dict"):
        return obj.to_dict()

    if hasattr(obj, "__dict__"):
        return obj.__dict__

    return obj


# ==============================================================================
# Dashboard
# ==============================================================================


def render_execution_audit_dashboard(
    db,
    portfolio_engine=None,
):

    st.title("📋 Institutional Execution Audit Dashboard")

    explorer = get_execution_event_explorer(
        db=db,
    )

    audit = get_execution_audit_engine(
        db=db,
    )

    validator = get_execution_event_stream_validator(
        db=db,
    )

    compliance = get_execution_compliance_engine(
        db=db,
    )

    metrics = get_execution_event_metrics(
        db=db,
    )

    time_machine = get_execution_event_time_machine(
        db=db,
    )

    # ======================================================================
    # Search
    # ======================================================================

    st.subheader("Search")

    c1, c2 = st.columns(2)

    with c1:

        entity = st.selectbox(

            "Entity",

            [

                "Execution",

                "Order",

                "Position",

                "Account",

                "Portfolio",

            ],

        )

    with c2:

        identifier = st.text_input(
            "Identifier",
        )

    filters = {}

    if identifier:

        if entity == "Execution":
            filters["execution_id"] = identifier

        elif entity == "Order":
            filters["broker_order_id"] = identifier

        elif entity == "Position":
            filters["position_id"] = identifier

        elif entity == "Account":
            filters["account_id"] = identifier

        else:
            filters["portfolio_id"] = identifier

    events = explorer.search(
        **filters,
    )

    timeline = explorer.timeline(
        **filters,
    )

    stats = explorer.statistics(
        **filters,
    )

    # ======================================================================
    # Navigation
    # ======================================================================

    workspace = st.radio(

        "Workspace",

        [

            "Summary",

            "Timeline",

            "Validation",

            "Compliance",

            "Metrics",

            "Event Details",

            "Replay",

            "Export",

        ],

        horizontal=True,

    )

    # ======================================================================
    # Summary
    # ======================================================================

    if workspace == "Summary":

        try:

            if entity == "Execution":

                report = audit.audit_execution(

                    execution_id=identifier,

                )

            elif entity == "Order":

                report = audit.audit_order(

                    broker_order_id=identifier,

                )

            elif entity == "Position":

                report = audit.audit_position(

                    position_id=identifier,

                )

            elif entity == "Account":

                report = audit.audit_account(

                    account_id=identifier,

                )

            else:

                report = audit.audit_portfolio(

                    portfolio_id=identifier,

                )

            summary = report.get(
                "summary",
                {},
            )

            c1, c2, c3, c4 = st.columns(4)

            c1.metric(
                "Events",
                report.get(
                    "event_count",
                    0,
                ),
            )

            c2.metric(
                "Entity",
                entity,
            )

            c3.metric(
                "Valid",
                "YES"
                if report.get(
                    "valid",
                    False,
                )
                else "NO",
            )

            c4.metric(

                "Anomalies",

                len(
                    report.get(
                        "anomalies",
                        [],
                    )
                ),

            )

            st.divider()

            st.json(
                summary,
            )

            if report.get(
                "anomalies"
            ):

                st.warning(
                    report[
                        "anomalies"
                    ]
                )

        except Exception as exc:

            st.error(exc)

    # ======================================================================
    # Timeline
    # ======================================================================

    elif workspace == "Timeline":

        st.subheader(
            "Audit Timeline"
        )

        if timeline:

            df = pd.DataFrame(
                timeline,
            )

            selected = st.selectbox(

                "Select Event",

                df.index,

                format_func=lambda i:
                f"{df.iloc[i]['sequence']:03d} "
                f"{df.iloc[i]['event']}",

            )

            st.dataframe(

                df,

                use_container_width=True,

                hide_index=True,

            )

            st.divider()

            st.json(
                events[selected],
            )

        else:

            st.info(
                "No events."
            )

    # ======================================================================
    # Validation
    # ======================================================================

    elif workspace == "Validation":

        try:

            if entity == "Execution":

                result = validator.validate_execution(
                    identifier,
                )

            elif entity == "Order":

                result = validator.validate_order(
                    identifier,
                )

            elif entity == "Position":

                result = validator.validate_position(
                    identifier,
                )

            elif entity == "Account":

                result = validator.validate_account(
                    identifier,
                )

            else:

                result = validator.validate_portfolio(
                    identifier,
                )

            st.json(
                _to_json(
                    result,
                ),
            )

        except Exception as exc:

            st.error(exc)

    # ======================================================================
    # Compliance
    # ======================================================================

    elif workspace == "Compliance":

        try:

            if entity == "Execution":

                result = compliance.evaluate_execution(

                    execution_id=identifier,

                )

            elif entity == "Order":

                result = compliance.evaluate_order(

                    broker_order_id=identifier,

                )

            elif entity == "Position":

                result = compliance.evaluate_position(

                    position_id=identifier,

                )

            elif entity == "Account":

                result = compliance.evaluate_account(

                    account_id=identifier,

                )

            else:

                result = compliance.evaluate_portfolio(

                    portfolio_id=identifier,

                )

            st.metric(

                "Compliance Score",

                result.score,

            )

            st.metric(

                "Checks",

                result.checks_run,

            )

            st.json(
                result.to_dict(),
            )

        except Exception as exc:

            st.error(exc)

    # ======================================================================
    # Metrics
    # ======================================================================

    elif workspace == "Metrics":

        st.subheader(
            "Execution Metrics"
        )

        st.json(

            metrics.aggregate_metrics(),

            expanded=False,

        )

    # ======================================================================
    # Event Details
    # ======================================================================

    elif workspace == "Event Details":

        if not events:

            st.info(
                "No events."
            )

        else:

            index = st.slider(

                "Event",

                0,

                len(events) - 1,

                0,

            )

            event = events[index]

            c1, c2 = st.columns(2)

            with c1:

                st.write(
                    "**Identifiers**"
                )

                st.write(
                    {

                        "Event":

                            event.get(
                                "event_id"
                            )
                            or event.get(
                                "id"
                            ),

                        "Execution":

                            event.get(
                                "execution_id"
                            ),

                        "Order":

                            event.get(
                                "broker_order_id"
                            ),

                        "Position":

                            event.get(
                                "position_id"
                            ),

                        "Account":

                            event.get(
                                "account_id"
                            ),

                        "Portfolio":

                            event.get(
                                "portfolio_id"
                            ),

                    }

                )

            with c2:

                st.write(
                    "**Metadata**"
                )

                st.write(
                    {

                        "Type":

                            event.get(
                                "event_type"
                            ),

                        "Status":

                            event.get(
                                "status"
                            ),

                        "Occurred":

                            event.get(
                                "occurred_at"
                            ),

                    }

                )

            st.divider()

            st.json(
                event,
                expanded=False,
            )

    # ======================================================================
    # Replay
    # ======================================================================

    elif workspace == "Replay":

        replay_time = st.text_input(

            "Replay Timestamp",

            datetime.utcnow().replace(
                microsecond=0,
            ).isoformat(),

        )

        if st.button(
            "Replay State",
        ):

            try:

                ts = datetime.fromisoformat(
                    replay_time,
                )

                if entity == "Execution":

                    ctx = time_machine.execution_at(

                        execution_id=identifier,

                        timestamp=ts,

                    )

                elif entity == "Order":

                    ctx = time_machine.order_at(

                        broker_order_id=identifier,

                        timestamp=ts,

                    )

                elif entity == "Position":

                    ctx = time_machine.position_at(

                        position_id=identifier,

                        timestamp=ts,

                    )

                elif entity == "Account":

                    ctx = time_machine.account_at(

                        account_id=identifier,

                        timestamp=ts,

                    )

                else:

                    ctx = time_machine.portfolio_at(

                        portfolio_id=identifier,

                        timestamp=ts,

                    )

                st.json(
                    _to_json(
                        ctx,
                    ),
                )

            except Exception as exc:

                st.error(exc)

    # ======================================================================
    # Export
    # ======================================================================

    elif workspace == "Export":

        export = st.selectbox(

            "Format",

            [

                "Timeline JSON",

                "Events JSON",

                "CSV",

            ],

        )

        if st.button(
            "Generate",
        ):

            if export == "Timeline JSON":

                payload = json.dumps(

                    timeline,

                    indent=4,

                    default=str,

                )

            elif export == "Events JSON":

                payload = explorer.export_json(
                    **filters,
                )

            else:

                payload = explorer.export_csv(
                    **filters,
                )

            st.download_button(

                "Download",

                payload,

                file_name=f"audit_{identifier}.txt",

                mime="text/plain",

            )

    st.divider()

    st.caption(
        "Institutional Execution Audit Dashboard • Sprint 40.4"
    )