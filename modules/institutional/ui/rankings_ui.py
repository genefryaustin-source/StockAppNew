import streamlit as st
import pandas as pd

from modules.analytics.rankings import (
    rank_symbols,
    sector_leaderboards,
    build_percentile_rankings,
)
from modules.market_data.service import build_shared_price_cache

from modules.analytics.alpha_engine import compute_sector_neutral_alpha
from modules.analytics.alpha_signals import build_alpha_signals
from modules.analytics.alpha_engine import build_top_opportunities


# ------------------------------------------------
# Symbol Filtering
# ------------------------------------------------

BAD_SUFFIX = ("W", "WS", "WT", "U", "R")


def filter_symbols(symbols):
    clean = []

    for s in symbols:
        if not isinstance(s, str):
            continue

        sym = s.strip().upper()

        if not sym:
            continue

        if sym.endswith(BAD_SUFFIX):
            continue

        clean.append(sym)

    return clean


# ------------------------------------------------
# Symbol Parsing
# ------------------------------------------------

def _parse_symbols(text: str):
    raw = [
        x.strip().upper()
        for x in text.replace("\n", ",").replace(" ", ",").split(",")
    ]

    raw = [x for x in raw if x]

    return filter_symbols(raw)


# ------------------------------------------------
# Rankings UI
# ------------------------------------------------

def render_rankings(db, user):

    tenant_id = user["tenant_id"]

    st.subheader("Rankings")

    st.caption(
        "Ranks tickers by latest stored AnalyticsSnapshot. "
        "Supports Percentile, Sector-Neutral Alpha, and Legacy Composite."
    )

    txt = st.text_area(
        "Symbols (comma/space/newline separated)",
        value="AAPL, MSFT, NVDA, TSLA, PLTR",
    )

    symbols = _parse_symbols(txt)

    if not symbols:
        st.warning("No valid symbols entered.")
        return

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        min_conf = st.slider("Min Confidence", 0, 100, 0, 5)

    with c2:
        top_n = st.slider("Top N", 5, 50, 15, 1)

    with c3:
        require_comp = st.checkbox("Require Composite", value=True)

    with c4:
        mode = st.selectbox(
            "Ranking Mode",
            ["Percentile", "Alpha", "Composite"],
            index=0,
        )

    c5, c6 = st.columns(2)

    with c5:
        sector_relative = st.checkbox(
            "Sector Relative Percentiles",
            value=False,
        )

    with c6:
        warm_cache = st.checkbox(
            "Warm Market Data Cache",
            value=True,
        )

    st.divider()

    st.caption(
        "Cache prevents repeated provider calls across modules."
    )

    # ------------------------------------------------
    # RUN RANKINGS (FIXED INDENTATION)
    # ------------------------------------------------

    if st.button("Run Rankings", type="primary"):

        # ---------------- CACHE ----------------
        if warm_cache:
            with st.spinner("Building shared market data cache..."):
                price_cache, meta = build_shared_price_cache(
                    db,
                    symbols,
                    min_rows=60,
                    max_api_calls=3,
                )

            if meta:
                st.caption(
                    f"Cache {len(meta.get('cache', []))} | "
                    f"API {len(meta.get('api', []))} | "
                    f"Failed {len(meta.get('failed', []))}"
                )

        # =====================================================
        # BASE DATA
        # =====================================================

        base_df = build_percentile_rankings(
            db=db,
            tenant_id=tenant_id,
            symbols=symbols,
            min_confidence=float(min_conf),
            sector_relative=sector_relative,
        )

        if base_df is None or base_df.empty:
            st.warning("No ranked results found. Run Analytics first.")
            return



            # =====================================================
            # MODE SWITCH
            # =====================================================

            # -------------------------------
            # PERCENTILE MODE
            # -------------------------------
        if mode == "Percentile":

            df = base_df.copy()

            df = df.sort_values(
                by=["percentile_composite", "confidence_score", "composite_score"],
                ascending=False
            ).head(top_n)

            display_cols = [
                "symbol",
                "sector",
                "rating",
                "percentile_composite",
                "quality_pct",
                "growth_pct",
                "value_pct",
                "momentum_pct",
                "risk_pct",
                "confidence_score",
            ]

            df = df[[c for c in display_cols if c in df.columns]]

            st.markdown("### Percentile Rankings")

            st.dataframe(df, use_container_width=True, hide_index=True)

            # -------------------------------
            # ALPHA MODE (FIXED)
            # -------------------------------
        elif mode == "Alpha":

            alpha_df = compute_sector_neutral_alpha(base_df)
            alpha_df = build_alpha_signals(alpha_df)

            if alpha_df is None or alpha_df.empty:
                st.warning("Alpha model returned no results.")
                return

            df = alpha_df.head(top_n)

            st.markdown("### Sector-Neutral Alpha Rankings")

            st.dataframe(df, use_container_width=True, hide_index=True)

            # =====================================================
            # 🚀 TOP OPPORTUNITIES (FIXED LOCATION)
            # =====================================================
            from modules.analytics.alpha_engine import build_top_opportunities

            st.divider()
            st.markdown("## 🚀 Top Opportunities")

            opps = build_top_opportunities(alpha_df, top_n=10)

            tab1, tab2, tab3, tab4 = st.tabs([
                "🟢 Undervalued",
                "🔵 Momentum",
                "🟡 Quality",
                "🔴 Overhyped"
            ])

            # -------------------------------
            # UNDERVALUED
            # -------------------------------
            with tab1:
                df = opps["undervalued"]

                if df.empty:
                    st.info("No strong undervalued signals")
                else:
                    st.dataframe(df[[
                        "symbol",
                        "sector",
                        "alpha_signal",
                        "alpha_score",
                        "alpha_minus_percentile",
                        "alpha_rationale"
                    ]], use_container_width=True, hide_index=True)

            # -------------------------------
            # MOMENTUM
            # -------------------------------
            with tab2:
                df = opps["momentum"]

                if df.empty:
                    st.info("No strong momentum signals")
                else:
                    st.dataframe(df[[
                        "symbol",
                        "sector",
                        "alpha_score",
                        "momentum_z",
                        "alpha_rationale"
                    ]], use_container_width=True, hide_index=True)

            # -------------------------------
            # QUALITY
            # -------------------------------
            with tab3:
                df = opps["quality"]

                if df.empty:
                    st.info("No quality leaders found")
                else:
                    st.dataframe(df[[
                        "symbol",
                        "sector",
                        "alpha_score",
                        "quality_z",
                        "risk_z",
                        "alpha_rationale"
                    ]], use_container_width=True, hide_index=True)

            # -------------------------------
            # OVERHYPED
            # -------------------------------
            with tab4:
                df = opps["overhyped"]

                if df.empty:
                    st.info("No overhyped signals")
                else:
                    st.dataframe(df[[
                        "symbol",
                        "sector",
                        "alpha_score",
                        "alpha_minus_percentile",
                        "alpha_rationale"
                    ]], use_container_width=True, hide_index=True)
            # -------------------------------
            # COMPOSITE MODE (NEW)
            # -------------------------------
        elif mode == "Composite":

            df = base_df.copy()

            if df is None or df.empty:
                st.warning("No composite data available.")
                return

            # Ensure composite exists
            if "composite_score" not in df.columns:
                st.error("Composite score not found in dataset.")
                st.write(df.columns)
                return

            # Sort by composite (primary), then confidence
            df = df.sort_values(
                by=["composite_score", "confidence_score"],
                ascending=False
            ).head(top_n)

            display_cols = [
                "symbol",
                "sector",
                "signal",
                "rating",
                "composite_score",
                "sentiment_score",
                "confidence_score",
                "quality_score",
                "growth_score",
                "value_score",
                "momentum_score",
                "risk_score",
            ]

            df = df[[c for c in display_cols if c in df.columns]]

            st.markdown("### 📊 Composite Rankings")

            st.dataframe(df, use_container_width=True, hide_index=True)


