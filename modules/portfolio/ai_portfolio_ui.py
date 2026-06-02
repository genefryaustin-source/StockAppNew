"""
modules/portfolio/ai_portfolio_ui.py

AI Portfolio Command Center UI

This page integrates:

- AI portfolio construction
- mission rotation
- regime detection
- predictive forecasting
- autonomous defense
- opportunity intelligence
- execution intelligence
- lifecycle intelligence
- reinforcement learning
- emergent strategies
- market simulation tournaments
"""

from __future__ import annotations

import traceback
from typing import Dict, Any, List

import pandas as pd
import streamlit as st

from modules.analytics.rankings import (
    rank_symbols,
)

from modules.analytics.ai_ranking_engine import (
    enhance_rankings_with_ai,
)

from modules.analytics.news_sentiment_engine import (
    build_sentiment_overlay_map,
)

from modules.market.regime_detection_engine import (
    detect_market_regime,
)

from modules.market.predictive_regime_engine import (
    forecast_market_regime,
)

from modules.portfolio.mission_rotation_engine import (
    select_optimal_mission,
    mission_transition_recommendations,
)



from modules.opportunity.opportunity_detection_engine import (
    detect_opportunity_signals,
    opportunities_to_dataframe,
)

from modules.execution.autonomous_execution_engine import (
    generate_execution_plan,
)

from modules.lifecycle.investment_lifecycle_engine import (
    track_investment_lifecycle,
    generate_lifecycle_actions,
)

from modules.reinforcement.reinforcement_learning_engine import (
    run_reinforcement_learning_cycle,
)

from modules.strategy.emergent_strategy_engine import (
    discover_emergent_strategies,
    emergent_strategies_to_dataframe,
)

from modules.simulation.market_simulation_engine import (
    generate_market_scenarios,
    run_strategy_tournament,
    scenarios_to_dataframe,
    tournament_to_dataframe,
)
from modules.risk.autonomous_defense_engine import (
    generate_defense_directive,
)
from modules.portfolio.portfolio_construction_ui import (
    render_portfolio_construction_panel,
)
from modules.portfolio.ai_portfolio_orchestrator import (
    AIPortfolioCandidate,
    construct_ai_portfolio,
)

# ---------------------------------------------------
# HELPERS
# ---------------------------------------------------

def _safe_float(
    value,
    default: float = 0.0,
) -> float:

    try:
        if value is None:
            return default

        return float(value)

    except Exception:
        return default


# ---------------------------------------------------
# MAIN UI
# ---------------------------------------------------

def render_ai_portfolio_center(
    db,
    user,
):

    st.title(
        "AI Portfolio Command Center"
    )

    st.info(
        "Autonomous portfolio intelligence center loaded."
    )

    try:

        tenant_id = user.get(
            "tenant_id"
        )

        # ---------------------------------------------------
        # LOAD RANKINGS
        # ---------------------------------------------------

        # Pull symbols from user's universe, fall back to defaults
        try:
            from modules.universe.models import UniverseSymbol
            _syms = (
                db.query(UniverseSymbol)
                .filter_by(tenant_id=tenant_id)
                .limit(100)
                .all()
            )
            symbols = [s.symbol for s in _syms if hasattr(s, "symbol") and s.symbol]
        except Exception:
            symbols = []

        if not symbols:
            symbols = [
                "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN",
                "META", "TSLA", "JPM", "V", "UNH", "BRK-B",
                "XOM", "JNJ", "PG", "MA", "HD", "AVGO", "MRK", "COST", "CVX",
            ]

        ranked_rows = rank_symbols(
            db=db,
            tenant_id=tenant_id,
            symbols=symbols,
        )

        if not ranked_rows:

            st.warning(
                "No AI rankings available."
            )

            return

        # ---------------------------------------------------
        # SENTIMENT OVERLAY
        # ---------------------------------------------------

        sentiment_overlay = (
            build_sentiment_overlay_map(
                ranked_rows
            )
        )

        # ---------------------------------------------------
        # AI ENHANCEMENT
        # ---------------------------------------------------

        ai_rows = (
            enhance_rankings_with_ai(
                ranked_rows,
                sentiment_overlay=(
                    sentiment_overlay
                ),
            )
        )

        # ---------------------------------------------------
        # REGIME DETECTION
        # ---------------------------------------------------

        regime_state = (
            detect_market_regime(
                volatility=35.0,
                breadth=58.0,
                sentiment=62.0,
                drawdown=8.0,
                liquidity_risk=32.0,
                downside_momentum=25.0,
                trend_strength=68.0,
                ai_confidence=72.0,
            )
        )

        # ---------------------------------------------------
        # FORECAST
        # ---------------------------------------------------

        forecast = (
            forecast_market_regime(
                current_state=(
                    regime_state
                ),
                volatility_trend=5.0,
                breadth_trend=3.0,
                sentiment_trend=4.0,
                liquidity_trend=2.0,
                momentum_trend=6.0,
            )
        )

        # ---------------------------------------------------
        # MISSION ROTATION
        # ---------------------------------------------------

        mission_decision = (
            select_optimal_mission(
                market_regime=(
                    regime_state.regime
                ),
                volatility=(
                    regime_state.stress_score
                ),
                sentiment=62.0,
                breadth=58.0,
                ai_confidence=72.0,
                portfolio_risk=42.0,
            )
        )

        # ---------------------------------------------------
        # DEFENSE DIRECTIVE
        # ---------------------------------------------------

        portfolio_risk_summary = {

            "portfolio_risk_score":
                42.0,

            "portfolio_volatility":
                28.0,

            "cash_buffer":
                8.0,

            "concentration_risk":
                "Moderate",

            "conviction_strength":
                "High",
        }

        defense = (
            generate_defense_directive(
                current_regime=(
                    regime_state.regime
                ),
                predictive_forecast=(
                    forecast
                ),
                portfolio_risk_summary=(
                    portfolio_risk_summary
                ),
                mission_decision=(
                    mission_decision
                ),
            )
        )

        # ---------------------------------------------------
        # OPPORTUNITY SIGNALS
        # ---------------------------------------------------

        opportunities = (
            detect_opportunity_signals(
                rows=ai_rows,
                sentiment_overlay=(
                    sentiment_overlay
                ),
                market_regime=(
                    regime_state.regime
                ),
                predictive_forecast=(
                    forecast
                ),
                max_results=15,
            )
        )

        # ---------------------------------------------------
        # PORTFOLIO CONSTRUCTION
        # ---------------------------------------------------
        def _get(row, *keys, default=0.0):
            """Get a value from either a dict or object, trying multiple key names."""
            for key in keys:
                if isinstance(row, dict):
                    val = row.get(key)
                else:
                    val = getattr(row, key, None)
                if val is not None:
                    try:
                        return val
                    except Exception:
                        pass
            return default

        portfolio_candidates = []
        for row in ai_rows:
            try:
                # Always convert to AIPortfolioCandidate so construct_ai_portfolio
                # gets objects with risk_adjusted_score / sizing_score properties
                c = AIPortfolioCandidate(
                    symbol=str(_get(row, "symbol", default="")),
                    sector=str(_get(row, "sector", default="Unknown") or "Unknown"),
                    ai_score=float(_get(row, "ai_score", "score", default=50) or 50),
                    consensus_score=float(_get(row, "consensus_score", "agent_consensus", default=50) or 50),
                    confidence=float(_get(row, "confidence", "ai_confidence", default=50) or 50),
                    risk_score=float(_get(row, "risk_score", "risk", default=50) or 50),
                    volatility=float(_get(row, "volatility", default=25) or 25),
                    expected_return=float(_get(row, "expected_return", default=0) or 0),
                    expected_alpha=float(_get(row, "expected_alpha", default=0) or 0),
                    downside_risk=float(_get(row, "downside_risk", default=0) or 0),
                    conviction_label=str(_get(row, "conviction_label", default="Neutral") or "Neutral"),
                    thesis=str(_get(row, "thesis", "ai_thesis", "rationale", default="") or ""),
                    bullish_factors=list(_get(row, "bullish_factors", default=[]) or []),
                    bearish_factors=list(_get(row, "bearish_factors", default=[]) or []),
                    risk_flags=list(_get(row, "risk_flags", default=[]) or []),
                )
                if c.symbol:
                    portfolio_candidates.append(c)
            except Exception:
                continue

        built_portfolio = []
        if portfolio_candidates:
            try:
                built_portfolio = construct_ai_portfolio(
                    candidates=portfolio_candidates,
                    max_positions=20,
                    max_position_weight=12.0,
                    sector_max_weight=30.0,
                    cash_buffer=5.0,
                )
            except Exception as _pe:
                st.warning(f"Portfolio construction warning: {_pe}")

        # ---------------------------------------------------
        # LAYOUT
        # ---------------------------------------------------

        tab0, tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([

            "🏗️ Portfolio",

            "Mission",

            "Defense",

            "Opportunities",

            "Execution",

            "Lifecycle",

            "Reinforcement",

            "Emergent Strategies",

            "Simulation",
        ])

        # ===================================================
        # PORTFOLIO CONSTRUCTION
        # ===================================================

        with tab0:
            render_portfolio_construction_panel(
                candidates=built_portfolio,
                mission_decision=mission_decision,
                regime_state=regime_state,
                opportunities=opportunities,
            )

        # ===================================================
        # MISSION
        # ===================================================

        with tab1:

            st.subheader(
                "Mission Rotation"
            )

            st.json(
                mission_decision.to_dict()
            )

            recommendations = (
                mission_transition_recommendations(
                    mission_decision
                )
            )

            if recommendations:

                st.markdown(
                    "### Recommendations"
                )

                for r in recommendations:

                    st.write(
                        f"• {r}"
                    )

            st.markdown(
                "### Market Regime"
            )

            st.json(
                regime_state.to_dict()
            )

            st.markdown(
                "### Predictive Forecast"
            )

            st.json(
                forecast.to_dict()
            )

        # ===================================================
        # DEFENSE
        # ===================================================

        with tab2:

            st.subheader(
                "Autonomous Defense Directive"
            )

            st.json(
                defense.to_dict()
            )

        # ===================================================
        # OPPORTUNITIES
        # ===================================================

        with tab3:

            st.subheader(
                "Opportunity Signals"
            )

            opp_df = (
                opportunities_to_dataframe(
                    opportunities
                )
            )

            st.dataframe(
                opp_df,
                use_container_width=True,
            )

        # ===================================================
        # EXECUTION
        # ===================================================

        with tab4:

            st.subheader(
                "Execution Intelligence"
            )

            execution_rows = []

            for opp in opportunities[:5]:

                plan = (
                    generate_execution_plan(
                        opportunity_signal=opp,
                        defense_directive=defense,
                        regime_forecast=forecast,
                        volatility_state=(
                            regime_state.volatility_state
                        ),
                    )
                )

                execution_rows.append(
                    plan.to_dict()
                )

            execution_df = (
                pd.DataFrame(
                    execution_rows
                )
            )

            st.dataframe(
                execution_df,
                use_container_width=True,
            )

        # ===================================================
        # LIFECYCLE
        # ===================================================

        with tab5:

            st.subheader(
                "Investment Lifecycle"
            )

            lifecycle_rows = []

            for opp in opportunities[:5]:

                lifecycle = (
                    track_investment_lifecycle(

                        symbol=opp.symbol,

                        entry_price=100.0,

                        current_price=112.0,

                        ai_confidence=(
                            opp.confidence
                        ),

                        sentiment_score=0.22,

                        momentum=68.0,

                        volatility=35.0,

                        regime_alignment=72.0,

                        benchmark_return=8.0,

                        realized_return=6.0,
                    )
                )

                actions = (
                    generate_lifecycle_actions(
                        lifecycle
                    )
                )

                row = (
                    lifecycle.to_dict()
                )

                row["actions"] = (
                    actions
                )

                lifecycle_rows.append(
                    row
                )

            lifecycle_df = (
                pd.DataFrame(
                    lifecycle_rows
                )
            )

            st.dataframe(
                lifecycle_df,
                use_container_width=True,
            )

        # ===================================================
        # REINFORCEMENT
        # ===================================================

        with tab6:

            st.subheader(
                "Reinforcement Learning"
            )

            rl_state = (
                run_reinforcement_learning_cycle(

                    strategy_name=(
                        "Adaptive Alpha Core"
                    ),

                    learning_cycle=1,

                    realized_alpha=12.0,

                    prediction_success=True,

                    execution_quality=82.0,

                    regime_aligned=True,

                    defense_preserved_capital=True,

                    opportunity_captured=True,

                    drawdown=5.0,

                    thesis_broken=False,

                    market_regime=(
                        regime_state.regime
                    ),
                )
            )

            st.json(
                rl_state.to_dict()
            )

        # ===================================================
        # EMERGENT STRATEGIES
        # ===================================================

        with tab7:

            st.subheader(
                "Emergent Strategies"
            )

            profiles = (
                discover_emergent_strategies(
                    reinforcement_states=[
                        rl_state
                    ],
                    opportunity_signals=(
                        opportunities
                    ),
                )
            )

            profile_df = (
                emergent_strategies_to_dataframe(
                    profiles
                )
            )

            st.dataframe(
                profile_df,
                use_container_width=True,
            )

        # ===================================================
        # SIMULATION
        # ===================================================

        with tab8:

            st.subheader(
                "Market Simulations"
            )

            scenarios = (
                generate_market_scenarios()
            )

            scenario_df = (
                scenarios_to_dataframe(
                    scenarios
                )
            )

            st.dataframe(
                scenario_df,
                use_container_width=True,
            )

            st.markdown(
                "### Strategy Tournament"
            )

            tournament = (
                run_strategy_tournament(
                    strategies=profiles,
                    scenarios=scenarios,
                )
            )

            tournament_df = (
                tournament_to_dataframe(
                    tournament
                )
            )

            st.dataframe(
                tournament_df,
                use_container_width=True,
            )

    except Exception as e:

        st.error(
            "AI Portfolio Command Center failed."
        )

        st.exception(e)

        traceback.print_exc()