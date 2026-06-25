# modules/forex/forex_carry_trade_dashboard.py

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

    from modules.forex.forex_carry_trade_engine import (
        ForexCarryTradeEngine,
        get_forex_carry_trade_engine,
    )

except Exception:

    from forex_service import (
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )

    from forex_carry_trade_engine import (
        ForexCarryTradeEngine,
        get_forex_carry_trade_engine,
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
            "No carry trade data available."
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

def render_forex_carry_trade_dashboard(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    engine: Optional[
        ForexCarryTradeEngine
    ] = None,
) -> None:

    engine = (
        engine
        or get_forex_carry_trade_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )
    )

    st.title(
        "Forex Carry Trade Dashboard"
    )

    st.caption(
        "Yield Differentials • Carry Opportunities • Global Rate Arbitrage Intelligence"
    )

    workspace = st.radio(
        "Carry Trade Workspace",
        [
            "Carry Scanner",
            "Pair Analysis",
            "Carry Matrix",
            "Rankings",
            "History",
        ],
        horizontal=True,
        key="carry_trade_workspace",
    )

    if workspace == "Carry Scanner":
        render_scanner(engine)

    elif workspace == "Pair Analysis":
        render_pair_analysis(engine)

    elif workspace == "Carry Matrix":
        render_matrix(engine)

    elif workspace == "Rankings":
        render_rankings(engine)

    elif workspace == "History":
        render_history(engine)


# ==========================================================
# Scanner
# ==========================================================

def render_scanner(
    engine: ForexCarryTradeEngine,
) -> None:

    st.subheader(
        "Global Carry Trade Scanner"
    )

    col1, col2 = st.columns(2)

    universe = col1.selectbox(
        "Pair Universe",
        [
            "Major Pairs",
            "Cross Pairs",
            "All Pairs",
        ],
        key="carry_universe",
    )

    save_scan = col2.checkbox(
        "Save Scan",
        value=True,
        key="carry_save_scan",
    )

    if universe == "Major Pairs":
        pairs = MAJOR_PAIRS

    elif universe == "Cross Pairs":
        pairs = CROSS_PAIRS

    else:
        pairs = DEFAULT_PAIRS

    if st.button(
        "Run Carry Trade Scan",
        use_container_width=True,
        key="carry_trade_scan_btn",
    ):

        with st.spinner(
            "Scanning carry opportunities..."
        ):

            scan = engine.scan_pairs(
                pairs=pairs,
                save=save_scan,
            )

            st.session_state[
                "carry_trade_scan"
            ] = scan.to_dict()

    scan = st.session_state.get(
        "carry_trade_scan"
    )

    if not scan:
        st.info(
            "Run a carry trade scan."
        )
        return

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Pairs",
        scan.get(
            "pair_count",
            0,
        ),
    )

    c2.metric(
        "Attractive",
        scan.get(
            "attractive_count",
            0,
        ),
    )

    c3.metric(
        "Neutral",
        scan.get(
            "neutral_count",
            0,
        ),
    )

    c4.metric(
        "Average Carry",
        scan.get(
            "average_carry_score",
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
            "base_currency",
            "quote_currency",
            "rate_differential",
            "carry_score",
            "conviction_score",
            "carry_regime",
            "carry_signal",
        ]
        if c in df.columns
    ]

    _grid(
        df[cols]
        if not df.empty
        else df,
        "carry_scan_grid",
    )


# ==========================================================
# Pair Analysis
# ==========================================================

def render_pair_analysis(
    engine: ForexCarryTradeEngine,
) -> None:

    st.subheader(
        "Carry Trade Analysis"
    )

    pair = st.text_input(
        "Currency Pair",
        value="AUD/JPY",
        key="carry_pair_input",
    )

    if st.button(
        "Analyze Carry Trade",
        use_container_width=True,
        key="carry_analysis_btn",
    ):

        snapshot = (
            engine.analyze_pair(
                pair,
                save=False,
            )
        )

        st.session_state[
            "carry_snapshot"
        ] = snapshot.to_dict()

    snapshot = st.session_state.get(
        "carry_snapshot"
    )

    if not snapshot:
        st.info(
            "Analyze a carry trade pair."
        )
        return

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Carry Score",
        snapshot.get(
            "carry_score",
            0,
        ),
    )

    c2.metric(
        "Rate Diff",
        snapshot.get(
            "rate_differential",
            0,
        ),
    )

    c3.metric(
        "Expected Carry",
        snapshot.get(
            "expected_carry_return",
            0,
        ),
    )

    c4.metric(
        "Conviction",
        snapshot.get(
            "conviction_score",
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

    chart_df = pd.DataFrame(
        [
            {
                "Factor": "Carry",
                "Score": snapshot.get(
                    "carry_score",
                    0,
                ),
            },
            {
                "Factor": "Yield",
                "Score": snapshot.get(
                    "yield_score",
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
                "Factor": "Intermarket",
                "Score": snapshot.get(
                    "intermarket_score",
                    0,
                ),
            },
            {
                "Factor": "Strength",
                "Score": snapshot.get(
                    "currency_strength_score",
                    0,
                ),
            },
        ]
    )

    fig = px.bar(
        chart_df,
        x="Factor",
        y="Score",
        title=f"{pair} Carry Components",
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
    engine: ForexCarryTradeEngine,
) -> None:

    st.subheader(
        "Carry Opportunity Matrix"
    )

    rows = engine.load_snapshots(
        limit=5000,
    )

    df = _df(rows)

    if df.empty:
        st.info(
            "No carry history available."
        )
        return

    if {
        "carry_score",
        "conviction_score",
    }.issubset(df.columns):

        fig = px.scatter(
            df,
            x="carry_score",
            y="conviction_score",
            color="carry_regime",
            size="rate_differential",
            hover_name="pair",
            title="Carry Opportunity Matrix",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    _grid(
        df,
        "carry_matrix_grid",
    )


# ==========================================================
# Rankings
# ==========================================================

def render_rankings(
    engine: ForexCarryTradeEngine,
) -> None:

    st.subheader(
        "Carry Trade Rankings"
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
            "conviction_score",
            ascending=False,
        )
        .head(25)
    )

    fig = px.bar(
        ranking_df,
        x="pair",
        y="conviction_score",
        color="carry_regime",
        title="Highest Conviction Carry Trades",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    fig2 = px.bar(
        ranking_df,
        x="pair",
        y="rate_differential",
        color="carry_regime",
        title="Interest Rate Differentials",
    )

    st.plotly_chart(
        fig2,
        use_container_width=True,
    )


# ==========================================================
# History
# ==========================================================

def render_history(
    engine: ForexCarryTradeEngine,
) -> None:

    st.subheader(
        "Carry Trade History"
    )

    pair_filter = st.text_input(
        "Pair Filter",
        value="",
        key="carry_history_filter",
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
        "carry_history_grid",
    )

    if {
        "created_at",
        "carry_score",
    }.issubset(df.columns):

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=df["created_at"],
                y=df["carry_score"],
                mode="lines+markers",
                name="Carry Score",
            )
        )

        fig.update_layout(
            title="Carry Trade Trend"
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

    render_forex_carry_trade_dashboard(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )