import streamlit as st
from modules.analytics.alpha_engine import compute_alpha_rank
from modules.analytics.rankings import build_percentile_rankings
from modules.analytics.snapshot_cache import get_latest_snapshots_df
import pandas as pd
from modules.analytics.rankings import (
    rank_symbols,
)
from modules.analytics.ai_ranking_engine import (
    enhance_rankings_with_ai,
    ai_rankings_to_dataframe,
)
from modules.analytics.news_provider import (
    get_news_batch,
)


from modules.analytics.earnings_nlp_engine import (
    analyze_earnings_batch,
    earnings_results_to_overlay_map,
    earnings_results_to_dataframe,
)

from modules.analytics.adaptive_factor_engine import (
    detect_market_regime,
    compute_adaptive_weights,
    adaptive_weights_to_dict,
)
from modules.analytics.news_sentiment_engine import (
    analyze_news_batch,
    sentiment_results_to_overlay_map,
    news_sentiment_to_dataframe,
)
from modules.analytics.research_agents import (
    evaluate_symbols_with_agents,
    consensus_results_to_overlay_map,
)
from modules.analytics.thesis_generation_engine import (
    generate_investment_thesis,
)

# -------------------------------------
# Helper
# -------------------------------------

def build_weight_dict(df):

    if df is None or df.empty:
        return {}

    df = df.dropna(subset=["Ticker", "weight"])

    weights = dict(zip(df["Ticker"], df["weight"]))

    return weights








# ----------------------------------------
# Render AI Rankings
# ----------------------------------------
def render_ai_rankings(db, user, price_data):

    st.subheader("AI-Enhanced Alpha Rankings")

    # -----------------------------------
    # Legacy cached price_data no longer required
    # Rankings now use analytics snapshots
    # -----------------------------------

    if price_data is None:
        price_data = {}

    # -----------------------------------
    # LOAD SNAPSHOTS → SECTOR MAP
    # -----------------------------------
    tenant_id = user.get("tenant_id")

    snapshot_df = get_latest_snapshots_df(db, tenant_id)

    sector_map = {}

    if snapshot_df is not None and not snapshot_df.empty:

        snapshot_df["symbol"] = snapshot_df["symbol"].astype(str).str.upper()

        if "sector" in snapshot_df.columns:
            sector_map = dict(zip(snapshot_df["symbol"], snapshot_df["sector"]))
        else:
            st.warning("No sector column found in snapshots")

    # DEBUG
    st.write("SECTOR MAP SIZE:", len(sector_map))

    # -----------------------------------
    # COMPUTE ALPHA (NOW SECTOR-NEUTRAL)
    # -----------------------------------
    symbols = (
        snapshot_df["symbol"]
        .dropna()
        .astype(str)
        .str.upper()
        .unique()
        .tolist()
    )
    st.write("SYMBOL COUNT:", len(symbols))
    # -----------------------------------
    # FETCH NEWS
    # -----------------------------------

    news_map = get_news_batch(
        symbols=symbols,
        days_back=7,
        max_symbols=100,
    )

    st.write(
        "NEWS SYMBOLS:",
        len(news_map),
    )
    # -----------------------------------
    # ANALYZE SENTIMENT
    # -----------------------------------

    sentiment_results = analyze_news_batch(
        news_map
    )

    sentiment_overlay = (
        sentiment_results_to_overlay_map(
            sentiment_results
        )
    )

    st.write(
        "SENTIMENT RESULTS:",
        len(sentiment_results),
    )
    # -----------------------------------
    # EARNINGS TRANSCRIPTS
    # -----------------------------------

    transcripts = {}

    for symbol in symbols[:50]:
        transcripts[symbol] = f"""
            The company reported strong demand and
            improving visibility. Management expressed
            confidence in long-term growth opportunities.
            However, macro uncertainty and margin
            pressure remain risks.
            """
    # -----------------------------------
    # ANALYZE EARNINGS NLP
    # -----------------------------------

    earnings_results = analyze_earnings_batch(
        transcripts
    )

    earnings_overlay = (
        earnings_results_to_overlay_map(
            earnings_results
        )
    )

    st.write(
        "EARNINGS NLP RESULTS:",
        len(earnings_results),
    )
    # -----------------------------------
    # MARKET REGIME DETECTION
    # -----------------------------------

    market_regime = detect_market_regime(

        market_return_30d=0.06,
        market_return_90d=0.11,

        volatility_30d=0.19,

        drawdown_90d=-0.04,
    )

    adaptive_weights = compute_adaptive_weights(
        regime=market_regime,
    )

    adaptive_weights_dict = (
        adaptive_weights_to_dict(
            adaptive_weights
        )
    )

    st.write(
        "MARKET REGIME:",
        market_regime.regime,
    )

    st.write(
        "ADAPTIVE WEIGHTS:",
        adaptive_weights_dict,
    )
    ranked_rows = rank_symbols(
        db=db,
        tenant_id=tenant_id,
        symbols=symbols,
    )

    if not ranked_rows:
        st.warning("No AI rankings available.")

        return
    from modules.analytics.research_agents import (
        evaluate_symbols_with_agents,
    )
    symbols_context = {}



    agent_results = evaluate_symbols_with_agents(
        symbols_context
    )
    # -----------------------------------
    # AI THESIS GENERATION
    # -----------------------------------

    thesis_results = {}

    for row in ranked_rows[:25]:

        try:

            consensus = agent_results.get(
                row.symbol
            )

            thesis = generate_investment_thesis(

                symbol=row.symbol,

                ai_score=row.composite,

                ai_confidence=row.confidence,

                consensus_score=(
                    consensus.consensus_score
                    if consensus else 50.0
                ),

                consensus_confidence=(
                    consensus.consensus_confidence
                    if consensus else 50.0
                ),

                bullish_factors=(
                    consensus.bullish_factors
                    if consensus else []
                ),

                bearish_factors=(
                    consensus.bearish_factors
                    if consensus else []
                ),

                risk_flags=(
                    consensus.risk_flags
                    if consensus else []
                ),

                sentiment_tone="positive",

                earnings_tone="constructive",

                guidance_score=65,

                ceo_confidence=70,

                risk_pressure=row.risk,

                market_regime=(
                    market_regime.regime
                ),

                volatility_level=(
                    market_regime.volatility_level
                ),

                momentum_state=(
                    market_regime.momentum_state
                ),
            )

            thesis_results[
                row.symbol
            ] = thesis

        except Exception as e:

            print(
                "THESIS GENERATION ERROR",
                row.symbol,
                e,
            )
    consensus_overlay = (
        consensus_results_to_overlay_map(
            agent_results
        )


    )
    ai_rows = enhance_rankings_with_ai(
        ranked_rows,
        sentiment_overlay=sentiment_overlay,
        earnings_overlay=earnings_overlay,
        adaptive_weights=adaptive_weights,
        consensus_overlay=consensus_overlay,
    )
    for row in ai_rows[:50]:
        symbols_context[row.symbol] = {
            "sector": row.sector,
            "quality": row.quality,
            "growth": row.growth,
            "value": row.value,
            "momentum": row.momentum,
            "risk": row.risk,
            "confidence": row.ai_confidence,
            "market_regime": market_regime.regime,
            "sentiment_score": sentiment_overlay.get(row.symbol, 0.0) * 100,
            "earnings_nlp": earnings_overlay.get(row.symbol, 0.0),
        }
    st.markdown("## Multi-Agent Research Consensus")

    agent_rows = []

    for symbol, result in agent_results.items():
        agent_rows.append({
            "Symbol": symbol,
            "Consensus Score": result.consensus_score,
            "Consensus Confidence": result.consensus_confidence,
            "Agents": result.agent_count,
            "Bullish Factors": ", ".join(result.bullish_factors),
            "Bearish Factors": ", ".join(result.bearish_factors),
            "Risk Flags": ", ".join(result.risk_flags),
        })

    agent_df = pd.DataFrame(agent_rows)

    if not agent_df.empty:
        st.dataframe(agent_df, use_container_width=True)
    else:
        st.info("No agent consensus results available.")
    # -----------------------------------
    # STORE
    # -----------------------------------

    st.session_state.rank_rows = ranked_rows

    # -----------------------------------
    # DATAFRAME
    # -----------------------------------

    rankings_df = ai_rankings_to_dataframe(
        ai_rows
    )

    # -----------------------------------
    # DISPLAY TABLE
    # -----------------------------------

    st.dataframe(
        rankings_df,
        use_container_width=True,
    )
    if "AI Score" in rankings_df.columns:
        rankings_df = rankings_df.sort_values(
            by="AI Score",
            ascending=False,
        )
    # -----------------------------------
    # TOP PICKS
    # -----------------------------------

    st.markdown("### Top AI Picks")

    st.dataframe(
        rankings_df.head(10),
        use_container_width=True,
    )
    st.markdown("## AI Analyst Narratives")

    for row in ai_rows[:10]:
        with st.expander(
                f"{row.symbol} — AI Score {row.ai_score}"
        ):
            st.markdown(
                f"### Bull Thesis\n\n"
                f"{row.bull_thesis}"
            )

            st.markdown(
                f"### Bear Thesis\n\n"
                f"{row.bear_thesis}"
            )

            st.markdown(
                f"### Risk Notes\n\n"
                f"{row.risk_notes}"
            )

            st.markdown(
                f"### AI Rationale\n\n"
                f"{row.ai_rationale}"
            )

            st.markdown(
                f"### Factor Summary\n\n"
                f"{row.factor_summary}"
            )

    # -----------------------------------
    # AI NEWS SENTIMENT
    # -----------------------------------

    st.markdown("## AI News Sentiment")

    sentiment_df = news_sentiment_to_dataframe(
        sentiment_results
    )

    if not sentiment_df.empty:

        sentiment_df = sentiment_df.sort_values(
            by="Sentiment Score",
            ascending=False,
        )

        st.dataframe(
            sentiment_df,
            use_container_width=True,
        )

        for _, row in sentiment_df.head(10).iterrows():
            with st.expander(
                    f"{row['Symbol']} — "
                    f"{row['Market Tone']}"
            ):
                st.markdown(
                    f"### Summary\n\n"
                    f"{row['Summary']}"
                )

                st.markdown(
                    f"### Bullish Catalysts\n\n"
                    f"{row['Catalysts']}"
                )

                st.markdown(
                    f"### Bearish Risks\n\n"
                    f"{row['Risks']}"
                )

                st.markdown(
                    f"### Confidence\n\n"
                    f"{row['Confidence']}"
                )

                st.markdown(
                    f"### Event Weight\n\n"
                    f"{row['Event Weight']}"
                )

    else:

        st.info(
            "No sentiment results available."
        )


    # -----------------------------------
    # EARNINGS NLP
    # -----------------------------------

    st.markdown("## Earnings Call NLP")

    earnings_df = earnings_results_to_dataframe(
        earnings_results
    )

    if not earnings_df.empty:

        st.dataframe(
            earnings_df,
            use_container_width=True,
        )

        for _, row in earnings_df.head(10).iterrows():
            with st.expander(
                    f"{row['Symbol']} — "
                    f"{row['Tone Shift']}"
            ):
                st.markdown(
                    f"### Executive Summary\n\n"
                    f"{row['Executive Summary']}"
                )

                st.markdown(
                    f"### Guidance Score\n\n"
                    f"{row['Guidance Score']}"
                )

                st.markdown(
                    f"### CEO Confidence\n\n"
                    f"{row['CEO Confidence']}"
                )

                st.markdown(
                    f"### Risk Pressure\n\n"
                    f"{row['Risk Pressure']}"
                )

                st.markdown(
                    f"### Analyst Sentiment\n\n"
                    f"{row['Analyst Sentiment']}"
                )

    else:

        st.info(
            "No earnings NLP results available."
        )

    # -----------------------------------
    # ADAPTIVE INTELLIGENCE
    # -----------------------------------

    st.markdown(
        "## Adaptive Market Intelligence"
    )

    st.markdown(
        f"""
        ### Current Market Regime

        **Regime:** {market_regime.regime}

        **Confidence:** {market_regime.confidence}

        **Volatility:** {market_regime.volatility_level}

        **Momentum State:** {market_regime.momentum_state}

        **Risk State:** {market_regime.risk_state}
        """
    )

    adaptive_df = pd.DataFrame([{
        "Factor": k,
        "Weight": v,
    } for k, v in adaptive_weights_dict.items()
        if isinstance(v, (int, float))
    ])

    st.dataframe(
        adaptive_df,
        use_container_width=True,
    )
    # -----------------------------------
    # AI INSTITUTIONAL THESIS
    # -----------------------------------

    st.markdown(
        "## AI Institutional Research Thesis"
    )

    for symbol, thesis in list(
            thesis_results.items()
    )[:10]:
        with st.expander(
                f"{symbol} — "
                f"{thesis.conviction_label}"
        ):
            st.markdown(
                f"### AI Thesis\n\n"
                f"{thesis.thesis}"
            )

            st.markdown(
                f"### Bull Case\n\n"
                f"{thesis.bull_case}"
            )

            st.markdown(
                f"### Bear Case\n\n"
                f"{thesis.bear_case}"
            )

            st.markdown(
                f"### Risk Outlook\n\n"
                f"{thesis.risk_outlook}"
            )

            st.markdown(
                f"### Macro Overlay\n\n"
                f"{thesis.macro_overlay}"
            )

            st.markdown(
                f"### Confidence Summary\n\n"
                f"{thesis.confidence_summary}"
            )