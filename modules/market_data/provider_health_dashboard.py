"""
modules/market_data/provider_health_dashboard.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.market_data.provider_router import (
    get_provider_router,
)

from modules.market_data.adaptive_rate_limit_manager import (
    get_rate_limit_manager,
)

from modules.market_data.provider_cache_manager import (
    get_provider_cache_status,
)


def _render_provider_summary(router):
    rows = router.get_status_rows()

    if not rows:
        st.info("No provider status available.")
        return

    df = pd.DataFrame(rows)

    total_providers = len(df)

    healthy = len(
        df[df["health_score"] >= 80]
    )

    degraded = len(
        df[
            (df["health_score"] >= 50)
            & (df["health_score"] < 80)
        ]
    )

    unhealthy = len(
        df[df["health_score"] < 50]
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            "Providers",
            total_providers,
        )

    with c2:
        st.metric(
            "Healthy",
            healthy,
        )

    with c3:
        st.metric(
            "Degraded",
            degraded,
        )

    with c4:
        st.metric(
            "Unhealthy",
            unhealthy,
        )


def _render_provider_table(router):
    rows = router.get_status_rows()

    if not rows:
        return

    df = pd.DataFrame(rows)

    st.subheader(
        "Provider Health Status"
    )

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )


def _render_rate_limit_status():
    manager = get_rate_limit_manager()

    rows = manager.rows()

    if not rows:
        return

    df = pd.DataFrame(rows)

    st.subheader(
        "Adaptive Rate Limit Manager"
    )

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )


def _render_cache_status(db):
    try:

        rows = get_provider_cache_status(db)

        if not rows:
            st.info(
                "No provider cache records found."
            )
            return

        df = pd.DataFrame(rows)

        st.subheader(
            "Provider Cache"
        )

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
        )

    except Exception as e:

        st.warning(
            f"Provider cache unavailable: {e}"
        )


def _render_provider_controls(router):
    st.subheader(
        "Provider Controls"
    )

    providers = router.all_providers()

    if not providers:
        return

    for provider in providers:

        col1, col2, col3, col4 = st.columns(
            [3, 1, 1, 1]
        )

        with col1:
            st.write(provider.provider)

        with col2:

            enabled = st.checkbox(
                "Enabled",
                value=provider.enabled,
                key=f"provider_enabled_{provider.provider}",
            )

            if enabled != provider.enabled:

                if enabled:
                    router.enable_provider(
                        provider.provider
                    )
                else:
                    router.disable_provider(
                        provider.provider
                    )

                st.rerun()

        with col3:

            if st.button(
                "Reset",
                key=f"provider_reset_{provider.provider}",
            ):
                router.reset_health(
                    provider.provider
                )
                st.rerun()

        with col4:

            st.write(
                f"{provider.health_score:.1f}"
            )


def _render_provider_rankings(router):
    st.subheader(
        "Provider Ranking Order"
    )

    ranked = router.get_ranked_providers()

    if not ranked:
        st.info(
            "No providers available."
        )
        return

    rows = []

    for idx, provider in enumerate(
        ranked,
        start=1,
    ):
        rows.append({
            "rank": idx,
            "provider": provider.provider,
            "health_score": provider.health_score,
            "enabled": provider.enabled,
            "success_count": provider.success_count,
            "failure_count": provider.failure_count,
            "rate_limit_count": provider.rate_limit_count,
        })

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
    )


def render_provider_health_dashboard(
    db,
):
    st.title(
        "Provider Health Dashboard"
    )

    router = get_provider_router()

    _render_provider_summary(
        router,
    )

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Health",
        "Rate Limits",
        "Cache",
        "Ranking",
        "Controls",
    ])

    with tab1:
        _render_provider_table(
            router,
        )

    with tab2:
        _render_rate_limit_status()

    with tab3:
        _render_cache_status(
            db,
        )

    with tab4:
        _render_provider_rankings(
            router,
        )

    with tab5:
        _render_provider_controls(
            router,
        )