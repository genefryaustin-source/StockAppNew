import streamlit as st
import pandas as pd

from modules.portfolio.black_litterman import black_litterman_weights
from modules.portfolio.risk_parity import risk_parity_weights
from modules.portfolio.rebalance_engine import compute_rebalance
from modules.portfolio.construction_engine import construct_portfolio

portfolio = construct_portfolio(
    alpha_df=alpha_df,
    method=method
)

st.dataframe(portfolio, use_container_width=True)

def render_portfolio_construction(db, user):
    st.write("SESSION KEYS:", list(st.session_state.keys()))
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
            "Risk Parity"
        ]
    )

    if st.button("Build Portfolio"):

        if model == "Black-Litterman":

            weights = black_litterman_weights(price_cache, symbols)

        else:

            weights = risk_parity_weights(price_cache, symbols)

        if weights is None:

            st.warning("Unable to compute weights")

            return

        st.markdown("### Target Weights")

        st.dataframe(weights, use_container_width=True)

        st.session_state.target_weights = weights
        
        st.markdown("## 🚀 Alpha Portfolio Construction")

        use_alpha = st.checkbox("Use Alpha Model", value=True)

        strategy = st.selectbox(
            "Alpha Strategy",
            ["undervalued", "momentum", "quality"]
        )

        top_n = st.slider("Portfolio Size", 5, 30, 10)

        if st.button("Build Alpha Portfolio"):

            from modules.analytics.alpha_engine import compute_sector_neutral_alpha
            from modules.analytics.alpha_signals import build_alpha_signals
            from modules.analytics.portfolio_optimizer import build_alpha_optimized_portfolio

            base_df = st.session_state.get("rank_base_df")

            if base_df is None:
                st.error("Run Rankings first")
                return

        alpha_df = compute_sector_neutral_alpha(base_df)
        alpha_df = build_alpha_signals(alpha_df)

        # filter strategy
        if strategy == "undervalued":
            alpha_df = alpha_df[
                (alpha_df["alpha_percentile"] >= 80) &
                (alpha_df["alpha_minus_percentile"] > 10)
            ]

        elif strategy == "momentum":
            alpha_df = alpha_df[
                (alpha_df["momentum_z"] > 1)
            ]

        elif strategy == "quality":
            alpha_df = alpha_df[
                (alpha_df["quality_z"] > 1)
            ]

        alpha_df = alpha_df.head(top_n)

        portfolio = build_alpha_optimized_portfolio(alpha_df)

        st.dataframe(portfolio, use_container_width=True)

        # store for deployment
        st.session_state["constructed_portfolio"] = portfolio

        method = st.selectbox(
            "Portfolio Method",
            ["alpha", "black_litterman", "risk_parity"]
        )

from modules.portfolio.black_litterman import optimize as bl_optimize

bl_portfolio = bl_optimize(weights)

st.subheader("Black-Litterman Portfolio")
st.write(bl_portfolio)

from modules.portfolio.risk_parity import optimize as rp_optimize

rp_portfolio = rp_optimize(weights)

st.subheader("Risk Parity Portfolio")
st.write(rp_portfolio)
