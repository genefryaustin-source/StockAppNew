"""
modules/execution/execution_replay_studio.py

Sprint 40.3

Institutional Execution Replay Studio

Interactive replay workstation built on the immutable execution
event stream.

This module is intentionally UI-only. It orchestrates the replay,
audit, validation, compliance, metrics, and projection engines.

The Replay Studio NEVER reads database tables directly.
"""

from __future__ import annotations

import json
from datetime import datetime

import pandas as pd
import streamlit as st

from modules.execution.execution_event_explorer import (
    get_execution_event_explorer,
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

from modules.execution.execution_event_projection import (
    get_execution_event_projection,
)

from modules.execution.execution_event_metrics import (
    get_execution_event_metrics,
)

from modules.execution.execution_event_stream_validator import (
    get_execution_event_stream_validator,
)


# ==============================================================================
# Helpers
# ==============================================================================


def _safe_call(fn, default=None):

    try:
        return fn()

    except Exception:
        return default


def _context_dict(context):

    if context is None:
        return {}

    if hasattr(context, "__dict__"):
        return dict(context.__dict__)

    return context


# ==============================================================================
# Replay Studio
# ==============================================================================


def render_execution_replay_studio(
    db,
    portfolio_engine=None,
):

    st.title("🎬 Execution Replay Studio")

    explorer = get_execution_event_explorer(
        db=db,
    )

    time_machine = get_execution_event_time_machine(
        db=db,
    )

    audit = get_execution_audit_engine(
        db=db,
    )

    compliance = get_execution_compliance_engine(
        db=db,
    )

    validator = get_execution_event_stream_validator(
        db=db,
    )

    projection = get_execution_event_projection(
        db=db,
    )

    metrics = get_execution_event_metrics(
        db=db,
    )

    # =====================================================================
    # Search
    # =====================================================================

    st.subheader("Replay Search")

    c1, c2 = st.columns(2)

    with c1:

        replay_type = st.selectbox(

            "Replay Target",

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

    replay_time = st.text_input(

        "Replay Timestamp (ISO8601)",

        datetime.utcnow().replace(
            microsecond=0,
        ).isoformat(),

    )

    # =====================================================================
    # Load Events
    # =====================================================================

    filters = {}

    if identifier:

        if replay_type == "Execution":
            filters["execution_id"] = identifier

        elif replay_type == "Order":
            filters["broker_order_id"] = identifier

        elif replay_type == "Position":
            filters["position_id"] = identifier

        elif replay_type == "Account":
            filters["account_id"] = identifier

        else:
            filters["portfolio_id"] = identifier

    events = explorer.search(
        **filters,
    )

    # =====================================================================
    # Timeline
    # =====================================================================

    st.subheader("Timeline")

    timeline = explorer.timeline(
        **filters,
    )

    if timeline:

        timeline_df = pd.DataFrame(
            timeline,
        )

        selection = st.selectbox(

            "Replay Event",

            timeline_df.index,

            format_func=lambda i:
            f"{timeline_df.iloc[i]['sequence']:03d} "
            f"{timeline_df.iloc[i]['event']} "
            f"{timeline_df.iloc[i]['timestamp']}",

        )

        st.dataframe(

            timeline_df,

            use_container_width=True,

            hide_index=True,

        )

    else:

        selection = None

        st.info(
            "No events found."
        )

    st.divider()

    # =====================================================================
    # Playback Controls
    # =====================================================================

    st.subheader("Playback")

    b1, b2, b3, b4 = st.columns(4)

    with b1:
        st.button("⏮ First")

    with b2:
        st.button("◀ Previous")

    with b3:
        st.button("▶ Next")

    with b4:
        st.button("⏭ Last")

    if timeline:

        slider = st.slider(

            "Timeline",

            min_value=0,

            max_value=len(timeline)-1,

            value=selection or 0,

        )

        replay_event = timeline[
            slider
        ]

        replay_timestamp = replay_event[
            "timestamp"
        ]

    else:

        replay_timestamp = None

    st.divider()

    # =====================================================================
    # Workspace
    # =====================================================================

    workspace = st.radio(

        "Workspace",

        [

            "Replay",

            "Context",

            "Audit",

            "Compliance",

            "Validation",

            "Metrics",

            "Projection Compare",

        ],

        horizontal=True,

    )

    # =====================================================================
    # Replay
    # =====================================================================

    if workspace == "Replay":

        if (
            identifier
            and replay_timestamp
        ):

            try:

                if replay_type == "Execution":

                    context = time_machine.execution_at(

                        execution_id=identifier,

                        timestamp=replay_timestamp,

                    )

                elif replay_type == "Order":

                    context = time_machine.order_at(

                        broker_order_id=identifier,

                        timestamp=replay_timestamp,

                    )

                elif replay_type == "Position":

                    context = time_machine.position_at(

                        position_id=identifier,

                        timestamp=replay_timestamp,

                    )

                elif replay_type == "Account":

                    context = time_machine.account_at(

                        account_id=identifier,

                        timestamp=replay_timestamp,

                    )

                else:

                    context = time_machine.portfolio_at(

                        portfolio_id=identifier,

                        timestamp=replay_timestamp,

                    )

                st.json(

                    _context_dict(
                        context,
                    ),

                    expanded=False,

                )

            except Exception as exc:

                st.error(exc)

    # =====================================================================
    # Context
    # =====================================================================

    elif workspace == "Context":

        if timeline:

            st.json(

                events[slider],

                expanded=False,

            )

    # =====================================================================
    # Audit
    # =====================================================================

    elif workspace == "Audit":

        try:

            if replay_type == "Execution":

                report = audit.audit_execution(

                    execution_id=identifier,

                )

            elif replay_type == "Order":

                report = audit.audit_order(

                    broker_order_id=identifier,

                )

            elif replay_type == "Position":

                report = audit.audit_position(

                    position_id=identifier,

                )

            elif replay_type == "Account":

                report = audit.audit_account(

                    account_id=identifier,

                )

            else:

                report = audit.audit_portfolio(

                    portfolio_id=identifier,

                )

            st.json(
                report,
            )

        except Exception as exc:

            st.error(exc)

    # =====================================================================
    # Compliance
    # =====================================================================

    elif workspace == "Compliance":

        try:

            if replay_type == "Execution":

                result = compliance.evaluate_execution(

                    execution_id=identifier,

                )

            elif replay_type == "Order":

                result = compliance.evaluate_order(

                    broker_order_id=identifier,

                )

            elif replay_type == "Position":

                result = compliance.evaluate_position(

                    position_id=identifier,

                )

            elif replay_type == "Account":

                result = compliance.evaluate_account(

                    account_id=identifier,

                )

            else:

                result = compliance.evaluate_portfolio(

                    portfolio_id=identifier,

                )

            st.json(
                result.to_dict(),
            )

        except Exception as exc:

            st.error(exc)

    # =====================================================================
    # Validation
    # =====================================================================

    elif workspace == "Validation":

        try:

            if replay_type == "Execution":

                validation = validator.validate_execution(
                    identifier,
                )

            elif replay_type == "Order":

                validation = validator.validate_order(
                    identifier,
                )

            elif replay_type == "Position":

                validation = validator.validate_position(
                    identifier,
                )

            elif replay_type == "Account":

                validation = validator.validate_account(
                    identifier,
                )

            else:

                validation = validator.validate_portfolio(
                    identifier,
                )

            if hasattr(validation, "to_dict"):

                st.json(
                    validation.to_dict(),
                )

            else:

                st.write(validation)

        except Exception as exc:

            st.error(exc)

    # =====================================================================
    # Metrics
    # =====================================================================

    elif workspace == "Metrics":

        st.json(

            metrics.aggregate_metrics(),

            expanded=False,

        )

    # =====================================================================
    # Projection Compare
    # =====================================================================

    elif workspace == "Projection Compare":

        st.subheader("Replay vs Projection")

        try:

            if replay_type == "Execution":

                projection_data = _safe_call(

                    lambda:
                    projection.rebuild_execution(
                        execution_id=identifier,
                    ),

                )

            elif replay_type == "Portfolio":

                projection_data = _safe_call(

                    lambda:
                    projection.rebuild_portfolio(
                        portfolio_id=identifier,
                    ),

                )

            else:

                projection_data = None

            st.write("Projection")

            st.write(projection_data)

            if (
                replay_timestamp
                and replay_type == "Execution"
            ):

                replay_context = time_machine.execution_at(

                    execution_id=identifier,

                    timestamp=replay_timestamp,

                )

                st.write("Replay")

                st.json(

                    _context_dict(
                        replay_context,
                    ),

                )

        except Exception as exc:

            st.error(exc)

    st.divider()

    # =====================================================================
    # Export
    # =====================================================================

    st.subheader("Export")

    export_type = st.selectbox(

        "Export",

        [

            "Timeline JSON",

            "Events JSON",

            "CSV",

        ],

    )

    if st.button(
        "Generate Export",
    ):

        try:

            if export_type == "Timeline JSON":

                payload = json.dumps(

                    timeline,

                    indent=4,

                    default=str,

                )

            elif export_type == "Events JSON":

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

                file_name=f"{identifier}.txt",

            )

        except Exception as exc:

            st.error(exc)

    st.caption(
        "Institutional Execution Replay Studio • Sprint 40.3"
    )