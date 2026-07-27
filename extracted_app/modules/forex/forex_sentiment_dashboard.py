# modules/forex/forex_sentiment_dashboard.py

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from typing import Any, Dict, List, Optional

try:
    from st_aggrid import (
        AgGrid,
        GridOptionsBuilder,
    )

    HAS_AGGRID = True

except Exception:
    HAS_AGGRID = False

try:
    from modules.forex.forex_service import (
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )

    from modules.forex.forex_sentiment_engine import (
        ForexSentimentEngine,
        get_forex_sentiment_engine,
    )

except Exception:

    from forex_service import (
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )

    from forex_sentiment_engine import (
        ForexSentimentEngine,
        get_forex_sentiment_engine,
    )


DEFAULT_PAIRS = MAJOR_PAIRS + CROSS_PAIRS


# ==========================================================
# Helpers
# ==========================================================

def _df(
    rows: List[Dict[str, Any]],
) -> pd.DataFrame:

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


def _grid(
    df: pd.DataFrame,
    key: str,
    height: int = 650,
) -> None:

    if df.empty:
        st.info(
            "No sentiment data available."
        )
        return

    if HAS_AGGRID:

        builder = (
            GridOptionsBuilder
            .from_dataframe(df)
        )

        builder.configure_default_column(
            sortable=True,
            filter=True,
            resizable=True,
        )

        builder.configure_pagination(
            enabled=True,
            paginationPageSize=25,
        )

        builder.configure_side_bar()

        AgGrid(
            df,
            gridOptions=builder.build(),
            fit_columns_on_grid_load=False,
            height=height,
            key=key,
        )

    else:

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            height=height,
        )


# ==========================================================
# Main Dashboard
# ==========================================================

def render_forex_sentiment_dashboard(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    engine: Optional[
        ForexSentimentEngine
    ] = None,
) -> None:

    engine = (
        engine
        or get_forex_sentiment_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )
    )

    st.title(
        "Forex Sentiment Dashboard"
    )

    st.caption(
        "News Sentiment • Policy Sentiment • Flow Sentiment • Institutional Positioning"
    )

    workspace = st.radio(
        "Sentiment Workspace",
        [
            "Sentiment Scanner",
            "Pair Analysis",
            "Sentiment Matrix",
            "Rankings",
            "History",
        ],
        horizontal=True,
        key="forex_sentiment_workspace",
    )

    if workspace == "Sentiment Scanner":
        render_scanner(engine)

    elif workspace == "Pair Analysis":
        render_pair_analysis(engine)

    elif workspace == "Sentiment Matrix":
        render_matrix(engine)

    elif workspace == "Rankings":
        render_rankings(engine)

    elif workspace == "History":
        render_history(engine)


# ==========================================================
# Scanner
# ==========================================================

def render_scanner(
    engine: ForexSentimentEngine,
) -> None:

    st.subheader(
        "Institutional Sentiment Scanner"
    )

    col1, col2 = st.columns(2)

    universe = col1.selectbox(
        "Pair Universe",
        [
            "Major Pairs",
            "Cross Pairs",
            "All Pairs",
        ],
        key="sentiment_universe",
    )

    save_scan = col2.checkbox(
        "Save Scan",
        value=True,
        key="sentiment_save_scan",
    )

    if universe == "Major Pairs":
        pairs = MAJOR_PAIRS

    elif universe == "Cross Pairs":
        pairs = CROSS_PAIRS

    else:
        pairs = DEFAULT_PAIRS

    if st.button(
        "Run Sentiment Scan",
        use_container_width=True,
        key="sentiment_scan_button",
    ):

        with st.spinner(
            "Analyzing forex sentiment..."
        ):

            scan = engine.scan_pairs(
                pairs=pairs,
                save=save_scan,
            )

            st.session_state[
                "forex_sentiment_scan"
            ] = scan.to_dict()

    scan = st.session_state.get(
        "forex_sentiment_scan"
    )

    if not scan:
        st.info(
            "Run a sentiment scan."
        )
        return

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Pairs",
        scan.get(
            "pair_count",
            0,
        ),
    )

    c2.metric(
        "Bullish",
        scan.get(
            "bullish_count",
            0,
        ),
    )

    c3.metric(
        "Bearish",
        scan.get(
            "bearish_count",
            0,
        ),
    )

    c4.metric(
        "Neutral",
        scan.get(
            "neutral_count",
            0,
        ),
    )

    c5.metric(
        "Avg Confidence",
        scan.get(
            "average_confidence",
            0,
        ),
    )

    df = _df(
        scan.get(
            "snapshots",
            [],
        )
    )

    cols = [
        c for c in [
            "pair",
            "sentiment_regime",
            "sentiment_signal",
            "net_sentiment_score",
            "sentiment_conviction_score",
            "confidence_score",
        ]
        if c in df.columns
    ]

    _grid(
        df[cols]
        if not df.empty
        else df,
        "sentiment_scan_grid",
    )


# ==========================================================
# Pair Analysis
# ==========================================================

def render_pair_analysis(
    engine: ForexSentimentEngine,
) -> None:

    st.subheader(
        "Pair Sentiment Analysis"
    )

    pair = st.text_input(
        "Currency Pair",
        value="EUR/USD",
        key="sentiment_pair_input",
    )

    if st.button(
        "Analyze Sentiment",
        use_container_width=True,
        key="sentiment_analysis_btn",
    ):

        snapshot = (
            engine.analyze_pair(
                pair,
                save=False,
            )
        )

        st.session_state[
            "sentiment_snapshot"
        ] = snapshot.to_dict()

    snapshot = st.session_state.get(
        "sentiment_snapshot"
    )

    if not snapshot:
        st.info(
            "Analyze a currency pair."
        )
        return

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Net Sentiment",
        snapshot.get(
            "net_sentiment_score",
            0,
        ),
    )

    c2.metric(
        "News",
        snapshot.get(
            "news_sentiment_score",
            0,
        ),
    )

    c3.metric(
        "Policy",
        snapshot.get(
            "policy_sentiment_score",
            0,
        ),
    )

    c4.metric(
        "Flow",
        snapshot.get(
            "flow_sentiment_score",
            0,
        ),
    )

    c5.metric(
        "Confidence",
        snapshot.get(
            "confidence_score",
            0,
        ),
    )

    factor_df = pd.DataFrame(
        [
            {
                "Factor": "News",
                "Score": snapshot.get(
                    "news_sentiment_score",
                    0,
                ),
            },
            {
                "Factor": "Policy",
                "Score": snapshot.get(
                    "policy_sentiment_score",
                    0,
                ),
            },
            {
                "Factor": "Flow",
                "Score": snapshot.get(
                    "flow_sentiment_score",
                    0,
                ),
            },
            {
                "Factor": "Strength",
                "Score": snapshot.get(
                    "strength_sentiment_score",
                    0,
                ),
            },
            {
                "Factor": "Momentum",
                "Score": snapshot.get(
                    "sentiment_momentum_score",
                    0,
                ),
            },
        ]
    )

    fig = px.bar(
        factor_df,
        x="Factor",
        y="Score",
        title=f"{pair} Sentiment Drivers",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    st.json(snapshot)


# ==========================================================
# Matrix
# ==========================================================

def render_matrix(
    engine: ForexSentimentEngine,
) -> None:

    st.subheader(
        "Sentiment Matrix"
    )

    rows = engine.load_snapshots(
        limit=5000,
    )

    df = _df(rows)

    if df.empty:
        st.info(
            "No sentiment history available."
        )
        return

    if {
        "net_sentiment_score",
        "confidence_score",
    }.issubset(df.columns):

        fig = px.scatter(
            df,
            x="net_sentiment_score",
            y="confidence_score",
            color="sentiment_regime",
            size="sentiment_conviction_score",
            hover_name="pair",
            title="Forex Sentiment Matrix",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    _grid(
        df,
        "sentiment_matrix_grid",
    )


# ==========================================================
# Rankings
# ==========================================================

def render_rankings(
    engine: ForexSentimentEngine,
) -> None:

    st.subheader(
        "Sentiment Rankings"
    )

    rows = engine.load_snapshots(
        limit=5000,
    )

    df = _df(rows)

    if df.empty:
        st.info(
            "No ranking data available."
        )
        return

    ranking_df = (
        df.sort_values(
            "sentiment_conviction_score",
            ascending=False,
        )
        .head(25)
    )

    fig = px.bar(
        ranking_df,
        x="pair",
        y="sentiment_conviction_score",
        color="sentiment_regime",
        title="Highest Conviction Sentiment Trades",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    fig2 = px.bar(
        ranking_df,
        x="pair",
        y="net_sentiment_score",
        color="sentiment_regime",
        title="Net Sentiment Ranking",
    )

    st.plotly_chart(
        fig2,
        use_container_width=True,
    )


# ==========================================================
# History
# ==========================================================

def render_history(
    engine: ForexSentimentEngine,
) -> None:

    st.subheader(
        "Sentiment History"
    )

    pair_filter = st.text_input(
        "Pair Filter",
        value="",
        key="sentiment_history_filter",
    )

    rows = engine.load_snapshots(
        pair=(
            pair_filter
            if pair_filter
            else None
        ),
        limit=5000,
    )

    df = _df(rows)

    if df.empty:
        st.info(
            "No history available."
        )
        return

    _grid(
        df,
        "sentiment_history_grid",
    )

    if {
        "created_at",
        "net_sentiment_score",
    }.issubset(df.columns):

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=df["created_at"],
                y=df[
                    "net_sentiment_score"
                ],
                mode="lines+markers",
                name="Net Sentiment",
            )
        )

        fig.update_layout(
            title="Sentiment Trend"
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )


# ==========================================================
# Public Entry Point
# ==========================================================

def render(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
) -> None:

    render_forex_sentiment_dashboard(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )