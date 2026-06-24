import streamlit as st
import pandas as pd
from datetime import datetime

from modules.portfolio.black_litterman import black_litterman_weights
from modules.portfolio.risk_parity import risk_parity_weights


def _render_save_section(db, user, df, symbol_col, key_prefix):
    """Save-to-watchlist / save-as-portfolio actions for a weights table.
    Shared by both the Black-Litterman/Risk Parity result and the Alpha
    Portfolio result below -- same pattern as the Portfolio Construction
    page (construction_engine.py).
    """
    st.markdown("### Save This Portfolio")
    st.caption(
        "Save these names to a watchlist to track them, or create a portfolio "
        "you can select from the Portfolio Deployment page to act on these weights."
    )

    if db is None or user is None:
        st.info("Save options require a database session.")
        return

    tenant_id = user.get("tenant_id")
    user_id = user.get("user_id")
    default_label = f"Portfolio Construction {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    col_wl, col_pf = st.columns(2)

    with col_wl:
        wl_name = st.text_input(
            "Watchlist name", value=default_label, key=f"{key_prefix}_wl_name"
        )
        if st.button(
            "📋 Save to Watchlist",
            key=f"{key_prefix}_save_watchlist",
            use_container_width=True,
        ):
            from modules.institutional.watchlists import create_watchlist, add_symbol

            try:
                tickers = df[symbol_col].astype(str).str.upper().tolist()
                wl = create_watchlist(db, tenant_id, wl_name, created_by_user_id=user_id)
                for tkr in tickers:
                    add_symbol(db, tenant_id, wl.id, tkr)
                st.success(f"Saved {len(tickers)} tickers to watchlist '{wl_name}'.")
            except Exception as e:
                db.rollback()
                st.error(f"Could not save watchlist: {e}")

    with col_pf:
        pf_name = st.text_input(
            "Portfolio name", value=default_label, key=f"{key_prefix}_pf_name"
        )
        if st.button(
            "💾 Save as Portfolio",
            key=f"{key_prefix}_save_portfolio",
            use_container_width=True,
        ):
            from modules.portfolio.service import create_portfolio

            try:
                create_portfolio(db, tenant_id, pf_name)
                st.success(
                    f"Created portfolio '{pf_name}'. Go to Portfolio Deployment, "
                    f"select it, and these target weights will be ready to deploy."
                )
            except Exception as e:
                db.rollback()
                st.error(f"Could not create portfolio: {e}")


def render_portfolio_construction(db, user):
    st.subheader("Portfolio Construction Lab")

    rows = st.session_state.get("rank_rows")
    price_cache = st.session_state.get("price_cache", {})

    if not rows:
        st.warning("Run AI Rankings first.")
        return

    symbols = [r.symbol for r in rows[:20]]

    model = st.selectbox(
        "Portfolio Model",
        [
            "Black-Litterman",
            "Risk Parity",
        ],
    )

    if st.button("Build Portfolio"):
        # price_cache (session-wide) may not have history loaded yet for
        # these symbols if nothing else has fetched them this session --
        # fall back to a live fetch for anything missing, same pattern used
        # on the Portfolio Deployment page.
        def _has_data(v):
            return v is not None and not getattr(v, "empty", True)

        local_price_cache = dict(price_cache)
        missing = [s for s in symbols if not _has_data(local_price_cache.get(s))]

        if missing:
            from modules.market_data.service import get_price_history

            for s in missing:
                df = get_price_history(db, s, period="1y")
                if _has_data(df):
                    local_price_cache[s] = df

        if model == "Black-Litterman":
            weights = black_litterman_weights(local_price_cache, symbols)
        else:
            weights = risk_parity_weights(local_price_cache, symbols)

        if weights is None:
            still_missing = [s for s in symbols if not _has_data(local_price_cache.get(s))]
            st.session_state["bl_rp_weights"] = None
            if still_missing:
                st.warning(
                    "No price history available for: "
                    + ", ".join(still_missing)
                    + ". Weights can't be computed until price data is available "
                    "(configure a market data provider, or visit a page that "
                    "loads price history for these symbols first)."
                )
            else:
                st.warning("Unable to compute weights")
        else:
            # Persist across reruns -- rendering the table and the save
            # buttons happens *outside* this `if st.button(...)` block (see
            # below), since clicking Save itself triggers a rerun where this
            # button is no longer "clicked", and anything nested in here
            # would otherwise vanish along with it.
            st.session_state["bl_rp_weights"] = weights
            st.session_state["target_weights"] = weights
            # also store under the key the Portfolio Deployment page reads --
            # weights already has "symbol"/"weight" columns, which the
            # deployment page's column-detection already recognizes.
            st.session_state["constructed_portfolio"] = weights

    bl_rp_weights = st.session_state.get("bl_rp_weights")
    if bl_rp_weights is not None:
        st.markdown("### Target Weights")
        st.dataframe(bl_rp_weights, use_container_width=True)
        _render_save_section(db, user, bl_rp_weights, "symbol", key_prefix="bl_rp")

    st.markdown("---")
    st.markdown("## 🚀 Alpha Portfolio Construction")

    use_alpha = st.checkbox("Use Alpha Model", value=True)

    strategy = st.selectbox(
        "Alpha Strategy",
        ["undervalued", "momentum", "quality"],
    )

    top_n = st.slider("Portfolio Size", 5, 30, 10)

    if st.button("Build Alpha Portfolio"):
        from modules.analytics.alpha_engine import compute_sector_neutral_alpha
        from modules.analytics.alpha_signals import build_alpha_signals
        from modules.analytics.portfolio_optimizer import build_alpha_optimized_portfolio

        # NOTE: "rank_base_df" is never set anywhere in this app -- AI Rankings
        # only ever populates "rank_rows" (a list of RankedRow objects). Build
        # the alpha engine's expected input from that instead, renaming fields
        # to the column names compute_sector_neutral_alpha actually expects
        # (it documents symbol/sector/rating/*_score/composite_score).
        if not rows:
            st.error("Run Rankings first")
            st.session_state["alpha_portfolio"] = None
        else:
            base_df = pd.DataFrame(rows).rename(columns={
                "quality": "quality_score",
                "growth": "growth_score",
                "value": "value_score",
                "momentum": "momentum_score",
                "risk": "risk_score",
                "confidence": "confidence_score",
                "composite": "composite_score",
                # compute_sector_neutral_alpha also looks for this exact name
                # to compute alpha_minus_percentile (the "undervalued" filter
                # below depends on it) -- RankedRow's equivalent field is
                # composite_pct.
                "composite_pct": "percentile_composite",
            })

            alpha_df = compute_sector_neutral_alpha(base_df)
            alpha_df = build_alpha_signals(alpha_df)

            # filter strategy
            if strategy == "undervalued":
                alpha_df = alpha_df[
                    (alpha_df["alpha_percentile"] >= 80)
                    & (alpha_df["alpha_minus_percentile"] > 10)
                ]
            elif strategy == "momentum":
                alpha_df = alpha_df[(alpha_df["momentum_z"] > 1)]
            elif strategy == "quality":
                alpha_df = alpha_df[(alpha_df["quality_z"] > 1)]

            alpha_df = alpha_df.head(top_n)

            portfolio = build_alpha_optimized_portfolio(alpha_df)

            if portfolio is None or portfolio.empty:
                st.session_state["alpha_portfolio"] = None
                st.warning(
                    f"No symbols matched the '{strategy}' strategy filter. "
                    "Try a different strategy or a larger portfolio size."
                )
            else:
                # Persist across reruns -- same reason as bl_rp_weights above:
                # the save buttons below trigger their own reruns, on which
                # this "Build Alpha Portfolio" button is no longer "clicked".
                st.session_state["alpha_portfolio"] = portfolio
                st.session_state["constructed_portfolio"] = portfolio

    alpha_portfolio = st.session_state.get("alpha_portfolio")
    if alpha_portfolio is not None:
        st.markdown("### Alpha-Optimized Portfolio")
        st.dataframe(alpha_portfolio, use_container_width=True)
        _render_save_section(db, user, alpha_portfolio, "symbol", key_prefix="alpha")