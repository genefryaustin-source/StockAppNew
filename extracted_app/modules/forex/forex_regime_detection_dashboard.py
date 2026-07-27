# modules/forex/forex_regime_detection_dashboard.py

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

    from modules.forex.forex_regime_detection_engine import (
        ForexRegimeDetectionEngine,
        get_forex_regime_detection_engine,
    )

except Exception:

    from forex_service import (
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )

    from forex_regime_detection_engine import (
        ForexRegimeDetectionEngine,
        get_forex_regime_detection_engine,
    )


DEFAULT_PAIRS = MAJOR_PAIRS + CROSS_PAIRS


# =========================================================
# Helpers
# =========================================================

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
            "No regime data available."
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


# =========================================================
# Main Dashboard
# =========================================================

def render_forex_regime_detection_dashboard(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    engine: Optional[
        ForexRegimeDetectionEngine
    ] = None,
) -> None:

    engine = (
        engine
        or get_forex_regime_detection_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )
    )

    st.title(
        "Forex Regime Detection Dashboard"
    )

    st.caption(
        "Market Regimes • Trend Detection • Volatility Expansion • Risk-On / Risk-Off Intelligence"
    )

    workspace = st.radio(
        "Regime Detection Workspace",
        [
            "Regime Scanner",
            "Pair Analysis",
            "Regime Matrix",
            "Regime Distribution",
            "History",
        ],
        horizontal=True,
        key="forex_regime_workspace",
    )

    if workspace == "Regime Scanner":
        render_scanner(engine)

    elif workspace == "Pair Analysis":
        render_pair_analysis(engine)

    elif workspace == "Regime Matrix":
        render_matrix(engine)

    elif workspace == "Regime Distribution":
        render_distribution(engine)

    elif workspace == "History":
        render_history(engine)


# =========================================================
# Scanner
# =========================================================

def render_scanner(
    engine: ForexRegimeDetectionEngine,
) -> None:

    st.subheader(
        "Market Regime Scanner"
    )

    col1, col2 = st.columns(2)

    universe = col1.selectbox(
        "Pair Universe",
        [
            "Major Pairs",
            "Cross Pairs",
            "All Pairs",
        ],
        key="regime_universe",
    )

    save_scan = col2.checkbox(
        "Save Scan",
        value=True,
        key="regime_save_scan",
    )

    if universe == "Major Pairs":
        pairs = MAJOR_PAIRS

    elif universe == "Cross Pairs":
        pairs = CROSS_PAIRS

    else:
        pairs = DEFAULT_PAIRS

    if st.button(
        "Run Regime Scan",
        use_container_width=True,
        key="run_regime_scan",
    ):

        with st.spinner(
            "Detecting market regimes..."
        ):

            scan = engine.scan_pairs(
                pairs=pairs,
                save=save_scan,
            )

            st.session_state[
                "forex_regime_scan"
            ] = scan.to_dict()

    scan = st.session_state.get(
        "forex_regime_scan"
    )

    if not scan:
        st.info(
            "Run a regime scan."
        )
        return

    c1, c2, c3, c4, c5, c6 = st.columns(6)

    c1.metric(
        "Pairs",
        scan.get(
            "pair_count",
            0,
        ),
    )

    c2.metric(
        "Trending",
        scan.get(
            "trending_count",
            0,
        ),
    )

    c3.metric(
        "Range",
        scan.get(
            "range_count",
            0,
        ),
    )

    c4.metric(
        "Breakout",
        scan.get(
            "breakout_count",
            0,
        ),
    )

    c5.metric(
        "Risk-Off",
        scan.get(
            "risk_off_count",
            0,
        ),
    )

    c6.metric(
        "Avg Score",
        scan.get(
            "average_regime_score",
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
            "market_regime",
            "regime_signal",
            "composite_regime_score",
            "trend_score",
            "flow_score",
            "strength_score",
            "confidence_score",
        ]
        if c in df.columns
    ]

    _grid(
        df[cols]
        if not df.empty
        else df,
        "regime_scan_grid",
    )


# =========================================================
# Pair Analysis
# =========================================================

def render_pair_analysis(
    engine: ForexRegimeDetectionEngine,
) -> None:

    st.subheader(
        "Pair Regime Analysis"
    )

    pair = st.text_input(
        "Currency Pair",
        value="EUR/USD",
        key="regime_pair_input",
    )

    if st.button(
        "Analyze Regime",
        use_container_width=True,
        key="analyze_regime_button",
    ):

        snapshot = engine.analyze_pair(
            pair,
            save=False,
        )

        st.session_state[
            "regime_snapshot"
        ] = snapshot.to_dict()

    snapshot = st.session_state.get(
        "regime_snapshot"
    )

    if not snapshot:
        st.info(
            "Analyze a currency pair."
        )
        return

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Trend",
        snapshot.get(
            "trend_score",
            0,
        ),
    )

    c2.metric(
        "Flow",
        snapshot.get(
            "flow_score",
            0,
        ),
    )

    c3.metric(
        "Strength",
        snapshot.get(
            "strength_score",
            0,
        ),
    )

    c4.metric(
        "Regime",
        snapshot.get(
            "composite_regime_score",
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
                "Factor": "Trend",
                "Score": snapshot.get(
                    "trend_score",
                    0,
                ),
            },
            {
                "Factor": "Flow",
                "Score": snapshot.get(
                    "flow_score",
                    0,
                ),
            },
            {
                "Factor": "Strength",
                "Score": snapshot.get(
                    "strength_score",
                    0,
                ),
            },
            {
                "Factor": "Correlation",
                "Score": snapshot.get(
                    "correlation_score",
                    0,
                ),
            },
            {
                "Factor": "Volatility",
                "Score": snapshot.get(
                    "volatility_regime_score",
                    0,
                ),
            },
            {
                "Factor": "Liquidity",
                "Score": snapshot.get(
                    "liquidity_regime_score",
                    0,
                ),
            },
        ]
    )

    fig = px.bar(
        factor_df,
        x="Factor",
        y="Score",
        title=f"{pair} Regime Factors",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    st.json(snapshot)


# =========================================================
# Matrix
# =========================================================

def render_matrix(
    engine: ForexRegimeDetectionEngine,
) -> None:

    st.subheader(
        "Regime Matrix"
    )

    rows = engine.load_snapshots(
        limit=5000,
    )

    df = _df(rows)

    if df.empty:
        st.info(
            "No regime history available."
        )
        return

    if {
        "composite_regime_score",
        "confidence_score",
    }.issubset(df.columns):

        fig = px.scatter(
            df,
            x="composite_regime_score",
            y="confidence_score",
            color="market_regime",
            size="trend_score",
            hover_name="pair",
            title="Market Regime Matrix",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    _grid(
        df,
        "regime_matrix_grid",
    )


# =========================================================
# Distribution
# =========================================================

def render_distribution(
    engine: ForexRegimeDetectionEngine,
) -> None:

    st.subheader(
        "Regime Distribution"
    )

    rows = engine.load_snapshots(
        limit=5000,
    )

    df = _df(rows)

    if df.empty:
        st.info(
            "No regime distribution available."
        )
        return

    if "market_regime" in df.columns:

        regime_counts = (
            df.groupby(
                "market_regime"
            )
            .size()
            .reset_index(
                name="count"
            )
        )

        fig = px.pie(
            regime_counts,
            names="market_regime",
            values="count",
            title="Market Regime Distribution",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    if {
        "pair",
        "composite_regime_score",
    }.issubset(df.columns):

        fig2 = px.bar(
            df.sort_values(
                "composite_regime_score",
                ascending=False,
            ).head(20),
            x="pair",
            y="composite_regime_score",
            color="market_regime",
            title="Top Regime Scores",
        )

        st.plotly_chart(
            fig2,
            use_container_width=True,
        )


# =========================================================
# History
# =========================================================

def render_history(
    engine: ForexRegimeDetectionEngine,
) -> None:

    st.subheader(
        "Regime History"
    )

    pair_filter = st.text_input(
        "Pair Filter",
        value="",
        key="regime_history_pair",
    )

    rows = engine.load_snapshots(
        pair=pair_filter if pair_filter else None,
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
        "regime_history_grid",
    )

    if {
        "created_at",
        "composite_regime_score",
    }.issubset(df.columns):

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=df["created_at"],
                y=df[
                    "composite_regime_score"
                ],
                mode="lines+markers",
                name="Regime Score",
            )
        )

        fig.update_layout(
            title="Regime Trend"
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )


# =========================================================
# Public Entry Point
# =========================================================

def render(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
) -> None:

    render_forex_regime_detection_dashboard(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )