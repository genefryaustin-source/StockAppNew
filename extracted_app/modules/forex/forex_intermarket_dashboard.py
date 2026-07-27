# modules/forex/forex_intermarket_dashboard.py

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

    from modules.forex.forex_intermarket_engine import (
        ForexIntermarketEngine,
        get_forex_intermarket_engine,
    )

except Exception:

    from forex_service import (
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )

    from forex_intermarket_engine import (
        ForexIntermarketEngine,
        get_forex_intermarket_engine,
    )


DEFAULT_PAIRS = MAJOR_PAIRS + CROSS_PAIRS


# ============================================================
# Helpers
# ============================================================

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
            "No intermarket data available."
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


# ============================================================
# Main Dashboard
# ============================================================

def render_forex_intermarket_dashboard(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    engine: Optional[
        ForexIntermarketEngine
    ] = None,
) -> None:

    engine = (
        engine
        or get_forex_intermarket_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )
    )

    st.title(
        "Forex Intermarket Dashboard"
    )

    st.caption(
        "Dollar • Rates • Equities • Commodities • Crypto Alignment Intelligence"
    )

    workspace = st.radio(
        "Intermarket Workspace",
        [
            "Intermarket Scanner",
            "Pair Analysis",
            "Alignment Matrix",
            "Rankings",
            "History",
        ],
        horizontal=True,
        key="forex_intermarket_workspace",
    )

    if workspace == "Intermarket Scanner":
        render_scanner(engine)

    elif workspace == "Pair Analysis":
        render_pair_analysis(engine)

    elif workspace == "Alignment Matrix":
        render_matrix(engine)

    elif workspace == "Rankings":
        render_rankings(engine)

    elif workspace == "History":
        render_history(engine)


# ============================================================
# Scanner
# ============================================================

def render_scanner(
    engine: ForexIntermarketEngine,
) -> None:

    st.subheader(
        "Institutional Intermarket Scanner"
    )

    col1, col2 = st.columns(2)

    universe = col1.selectbox(
        "Pair Universe",
        [
            "Major Pairs",
            "Cross Pairs",
            "All Pairs",
        ],
        key="intermarket_universe",
    )

    save_scan = col2.checkbox(
        "Save Scan",
        value=True,
        key="intermarket_save_scan",
    )

    if universe == "Major Pairs":
        pairs = MAJOR_PAIRS

    elif universe == "Cross Pairs":
        pairs = CROSS_PAIRS

    else:
        pairs = DEFAULT_PAIRS

    if st.button(
        "Run Intermarket Scan",
        use_container_width=True,
        key="run_intermarket_scan",
    ):

        with st.spinner(
            "Analyzing cross-asset alignment..."
        ):

            scan = engine.scan_pairs(
                pairs=pairs,
                save=save_scan,
            )

            st.session_state[
                "forex_intermarket_scan"
            ] = scan.to_dict()

    scan = st.session_state.get(
        "forex_intermarket_scan"
    )

    if not scan:
        st.info(
            "Run an intermarket scan."
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
        "Avg Score",
        scan.get(
            "average_score",
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
            "intermarket_score",
            "confidence_score",
            "intermarket_regime",
            "intermarket_signal",
            "currency_strength_score",
            "capital_flow_score",
            "regime_score",
        ]
        if c in df.columns
    ]

    _grid(
        df[cols]
        if not df.empty
        else df,
        "intermarket_scan_grid",
    )


# ============================================================
# Pair Analysis
# ============================================================

def render_pair_analysis(
    engine: ForexIntermarketEngine,
) -> None:

    st.subheader(
        "Intermarket Pair Analysis"
    )

    pair = st.text_input(
        "Currency Pair",
        value="EUR/USD",
        key="intermarket_pair",
    )

    if st.button(
        "Analyze Intermarket Alignment",
        use_container_width=True,
        key="intermarket_analysis_button",
    ):

        snapshot = (
            engine.analyze_pair(
                pair,
                save=False,
            )
        )

        st.session_state[
            "intermarket_snapshot"
        ] = snapshot.to_dict()

    snapshot = st.session_state.get(
        "intermarket_snapshot"
    )

    if not snapshot:
        st.info(
            "Analyze a currency pair."
        )
        return

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Intermarket",
        snapshot.get(
            "intermarket_score",
            0,
        ),
    )

    c2.metric(
        "Dollar",
        snapshot.get(
            "dollar_alignment_score",
            0,
        ),
    )

    c3.metric(
        "Rates",
        snapshot.get(
            "rates_alignment_score",
            0,
        ),
    )

    c4.metric(
        "Flows",
        snapshot.get(
            "capital_flow_score",
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
                "Factor": "Dollar",
                "Score": snapshot.get(
                    "dollar_alignment_score",
                    0,
                ),
            },
            {
                "Factor": "Rates",
                "Score": snapshot.get(
                    "rates_alignment_score",
                    0,
                ),
            },
            {
                "Factor": "Equities",
                "Score": snapshot.get(
                    "equity_alignment_score",
                    0,
                ),
            },
            {
                "Factor": "Commodities",
                "Score": snapshot.get(
                    "commodity_alignment_score",
                    0,
                ),
            },
            {
                "Factor": "Crypto",
                "Score": snapshot.get(
                    "crypto_alignment_score",
                    0,
                ),
            },
            {
                "Factor": "Regime",
                "Score": snapshot.get(
                    "regime_score",
                    0,
                ),
            },
        ]
    )

    fig = px.bar(
        chart_df,
        x="Factor",
        y="Score",
        title=f"{pair} Intermarket Factors",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    st.json(snapshot)


# ============================================================
# Matrix
# ============================================================

def render_matrix(
    engine: ForexIntermarketEngine,
) -> None:

    st.subheader(
        "Intermarket Alignment Matrix"
    )

    rows = engine.load_snapshots(
        limit=5000,
    )

    df = _df(rows)

    if df.empty:
        st.info(
            "No intermarket history available."
        )
        return

    if {
        "intermarket_score",
        "confidence_score",
    }.issubset(df.columns):

        fig = px.scatter(
            df,
            x="intermarket_score",
            y="confidence_score",
            color="intermarket_regime",
            size="capital_flow_score",
            hover_name="pair",
            title="Intermarket Alignment Matrix",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    _grid(
        df,
        "intermarket_matrix_grid",
    )


# ============================================================
# Rankings
# ============================================================

def render_rankings(
    engine: ForexIntermarketEngine,
) -> None:

    st.subheader(
        "Intermarket Rankings"
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
            "intermarket_score",
            ascending=False,
        )
        .head(20)
    )

    fig = px.bar(
        ranking_df,
        x="pair",
        y="intermarket_score",
        color="intermarket_regime",
        title="Top Intermarket Opportunities",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    fig2 = px.bar(
        ranking_df,
        x="pair",
        y="confidence_score",
        color="intermarket_regime",
        title="Intermarket Confidence Ranking",
    )

    st.plotly_chart(
        fig2,
        use_container_width=True,
    )


# ============================================================
# History
# ============================================================

def render_history(
    engine: ForexIntermarketEngine,
) -> None:

    st.subheader(
        "Intermarket History"
    )

    pair_filter = st.text_input(
        "Pair Filter",
        value="",
        key="intermarket_history_pair",
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
        "intermarket_history_grid",
    )

    if {
        "created_at",
        "intermarket_score",
    }.issubset(df.columns):

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=df["created_at"],
                y=df[
                    "intermarket_score"
                ],
                mode="lines+markers",
                name="Intermarket Score",
            )
        )

        fig.update_layout(
            title="Intermarket Trend"
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )


# ============================================================
# Public Entry Point
# ============================================================

def render(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
) -> None:

    render_forex_intermarket_dashboard(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )