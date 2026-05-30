"""
modules/core/cache_invalidation.py
"""

from __future__ import annotations

import streamlit as st


def invalidate_all_app_caches():

    """
    Clears:
    - Streamlit cache
    - session state cache
    - persistent DiskCache market data
    - analytics/UI cache layers

    Call after:
    - universe refresh
    - rankings rerun
    - analytics rerun
    - bulk cleanup
    - blacklist changes
    """

    # ---------------------------------
    # STREAMLIT CACHE
    # ---------------------------------
    try:

        st.cache_data.clear()

        print("✅ cache_data cleared")

    except Exception as e:

        print(
            "⚠️ cache_data clear failed:",
            e,
        )

    try:

        st.cache_resource.clear()

        print("✅ cache_resource cleared")

    except Exception as e:

        print(
            "⚠️ cache_resource clear failed:",
            e,
        )

    # ---------------------------------
    # DISKCACHE MARKET DATA CACHE
    # ---------------------------------
    try:

        from modules.market_data.service import (
            CACHE,
        )

        CACHE.clear()

        print("✅ DISKCACHE CLEARED")

    except Exception as e:

        print(
            "⚠️ DISKCACHE CLEAR FAILED:",
            e,
        )

    # ---------------------------------
    # SESSION STATE KEYS
    # ---------------------------------
    keys_to_clear = [

        # rankings
        "rank_rows",
        "latest_rankings_df",

        # analytics
        "analytics_cache",
        "analytics_df",
        "factor_cache",
        "snapshot_cache",
        "latest_snapshots_df",

        # universes
        "universe_rows",
        "universe_df",
        "universe_table",
        "latest_universe_df",
        "selected_universe",
        "selected_symbols",

        # market data
        "market_data_cache",

        # portfolios
        "portfolio_cache",

        # attribution
        "sector_attribution_cache",
        "benchmark_attribution_cache",
    ]

    for key in keys_to_clear:

        try:

            st.session_state.pop(
                key,
                None,
            )

        except Exception:
            pass

    # ---------------------------------
    # REFRESH VERSION
    # ---------------------------------
    try:

        st.session_state[
            "refresh_version"
        ] = (
            st.session_state.get(
                "refresh_version",
                0,
            ) + 1
        )

        print(
            "✅ refresh_version incremented:",
            st.session_state[
                "refresh_version"
            ]
        )

    except Exception as e:

        print(
            "⚠️ refresh_version failed:",
            e,
        )

    print(
        "✅ APP CACHE INVALIDATION COMPLETE"
    )