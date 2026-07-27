from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.platform.platform_validation_orchestrator import (
    run_platform_validation,
)


def _render_engine_summary(
    engine_statuses: dict[str, str],
    engine_scores: dict[str, float],
):

    rows = []

    for engine_name, status in engine_statuses.items():

        icon = {
            "PASS": "✅",
            "WARN": "⚠️",
            "FAIL": "❌",
        }.get(status, "•")

        rows.append({
            "Engine": engine_name.title(),
            "Status": f"{icon} {status}",
            "Score": round(
                float(
                    engine_scores.get(
                        engine_name,
                        0,
                    )
                ),
                2,
            ),
        })

    if rows:

        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
        )


def render_platform_validation_dashboard(
    db,
    tenant_id: str | None = None,
):

    st.subheader(
        "✅ Platform Validation Center"
    )

    st.caption(
        "Runs all platform validation engines."
    )

    if st.button(
        "Run Full Platform Validation",
        type="primary",
        key="platform_validation_run",
    ):

        with st.spinner(
            "Running platform validation..."
        ):

            st.session_state[
                "platform_validation_result"
            ] = run_platform_validation(
                db=db,
                tenant_id=tenant_id,
            )

    result = st.session_state.get(
        "platform_validation_result"
    )

    if not result:

        st.info(
            "Run validation to begin."
        )
        return

    totals = result.get(
        "totals",
        {},
    )

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Platform Score",
        f"{result.get('score',0):.2f}%"
    )

    c2.metric(
        "Status",
        result.get(
            "status",
            "UNKNOWN",
        ),
    )

    c3.metric(
        "PASS",
        totals.get(
            "PASS",
            0,
        ),
    )

    c4.metric(
        "WARN",
        totals.get(
            "WARN",
            0,
        ),
    )

    c5.metric(
        "FAIL",
        totals.get(
            "FAIL",
            0,
        ),
    )

    st.divider()

    st.markdown(
        "### Validation Engine Summary"
    )

    _render_engine_summary(
        result.get(
            "engine_statuses",
            {},
        ),
        result.get(
            "engine_scores",
            {},
        ),
    )

    st.divider()

    for engine in [
        "equities",
        "options",
        "portfolio",
        "providers",
    ]:

        engine_result = result.get(
            engine,
            {},
        )

        with st.expander(
            f"{engine.title()} Validation",
            expanded=False,
        ):

            st.metric(
                "Status",
                engine_result.get(
                    "status",
                    "UNKNOWN",
                ),
            )

            st.metric(
                "Score",
                engine_result.get(
                    "score",
                    0,
                ),
            )

            st.json(
                engine_result
            )

    with st.expander(
        "Raw Platform Validation Payload",
        expanded=False,
    ):

        st.json(result)