# modules/forex/forex_order_flow_dashboard.py

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from typing import Any, Dict, List, Optional

try:
    from st_aggrid import AgGrid, GridOptionsBuilder
    HAS_AGGRID = True
except Exception:
    HAS_AGGRID = False

try:
    from modules.forex.forex_order_flow_engine import (
        ForexOrderFlowEngine,
        get_forex_order_flow_engine,
    )
    from modules.forex.forex_service import (
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )
except Exception:
    from forex_order_flow_engine import (
        ForexOrderFlowEngine,
        get_forex_order_flow_engine,
    )
    from forex_service import (
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )


DEFAULT_PAIRS = MAJOR_PAIRS + CROSS_PAIRS


# ============================================================
# Helpers
# ============================================================

def _df(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _grid(
    df: pd.DataFrame,
    key: str,
    height: int = 600,
) -> None:

    if df.empty:
        st.info("No order flow data available.")
        return

    if HAS_AGGRID:

        builder = GridOptionsBuilder.from_dataframe(df)

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
# Dashboard
# ============================================================

def render_forex_order_flow_dashboard(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    order_flow_engine: Optional[
        ForexOrderFlowEngine
    ] = None,
) -> None:

    engine = (
        order_flow_engine
        or get_forex_order_flow_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )
    )

    st.title("Forex Order Flow Dashboard")

    st.caption(
        "Institutional Flow • Absorption • Sweeps • Imbalance • Liquidity"
    )

    workspace = st.radio(
        "Order Flow Workspace",
        [
            "Scanner",
            "Pair Analysis",
            "Flow Rankings",
            "Analytics",
            "History",
        ],
        horizontal=True,
        key="forex_order_flow_workspace",
    )

    if workspace == "Scanner":
        render_scanner(engine)

    elif workspace == "Pair Analysis":
        render_pair_analysis(engine)

    elif workspace == "Flow Rankings":
        render_rankings(engine)

    elif workspace == "Analytics":
        render_analytics(engine)

    elif workspace == "History":
        render_history(engine)


# ============================================================
# Scanner
# ============================================================

def render_scanner(
    engine: ForexOrderFlowEngine,
) -> None:

    st.subheader(
        "Institutional Order Flow Scanner"
    )

    col1, col2 = st.columns(2)

    pair_group = col1.selectbox(
        "Pair Universe",
        [
            "Major Pairs",
            "Cross Pairs",
            "All Pairs",
        ],
        key="flow_pair_group",
    )

    save_scan = col2.checkbox(
        "Save Scan",
        value=True,
        key="flow_save_scan",
    )

    if pair_group == "Major Pairs":
        pairs = MAJOR_PAIRS

    elif pair_group == "Cross Pairs":
        pairs = CROSS_PAIRS

    else:
        pairs = DEFAULT_PAIRS

    if st.button(
        "Run Order Flow Scan",
        use_container_width=True,
        key="flow_scan_button",
    ):

        with st.spinner(
            "Analyzing institutional flow..."
        ):

            scan = engine.scan_pairs(
                pairs=pairs,
                save=save_scan,
            )

            st.session_state[
                "forex_order_flow_scan"
            ] = scan.to_dict()

    scan = st.session_state.get(
        "forex_order_flow_scan"
    )

    if not scan:
        st.info(
            "Run an order flow scan."
        )
        return

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Pairs",
        scan.get("pair_count", 0),
    )

    c2.metric(
        "Bullish",
        scan.get("bullish_count", 0),
    )

    c3.metric(
        "Bearish",
        scan.get("bearish_count", 0),
    )

    c4.metric(
        "Avg Imbalance",
        scan.get(
            "avg_imbalance_score",
            0,
        ),
    )

    c5.metric(
        "Avg Confidence",
        scan.get(
            "avg_confidence_score",
            0,
        ),
    )

    st.divider()

    df = _df(
        scan.get(
            "snapshots",
            [],
        )
    )

    display_cols = [
        c
        for c in [
            "pair",
            "price",
            "buy_pressure",
            "sell_pressure",
            "imbalance_score",
            "absorption_score",
            "sweep_score",
            "liquidity_score",
            "flow_direction",
            "flow_signal",
            "confidence_score",
        ]
        if c in df.columns
    ]

    _grid(
        df[display_cols]
        if not df.empty
        else df,
        "flow_scan_grid",
    )


# ============================================================
# Pair Analysis
# ============================================================

def render_pair_analysis(
    engine: ForexOrderFlowEngine,
) -> None:

    st.subheader(
        "Order Flow Pair Analysis"
    )

    col1, col2 = st.columns(2)

    pair = col1.text_input(
        "Currency Pair",
        value="EUR/USD",
        key="flow_pair_analysis",
    )

    save_snapshot = col2.checkbox(
        "Save Snapshot",
        value=True,
        key="flow_save_snapshot",
    )

    if st.button(
        "Analyze Pair",
        use_container_width=True,
        key="flow_pair_button",
    ):

        with st.spinner(
            "Analyzing order flow..."
        ):

            snapshot = engine.analyze_pair(
                pair,
                save=save_snapshot,
            )

            st.session_state[
                "forex_order_flow_snapshot"
            ] = snapshot.to_dict()

    snapshot = st.session_state.get(
        "forex_order_flow_snapshot"
    )

    if not snapshot:
        st.info(
            "Analyze a currency pair."
        )
        return

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Imbalance",
        snapshot.get(
            "imbalance_score",
            0,
        ),
    )

    c2.metric(
        "Liquidity",
        snapshot.get(
            "liquidity_score",
            0,
        ),
    )

    c3.metric(
        "Absorption",
        snapshot.get(
            "absorption_score",
            0,
        ),
    )

    c4.metric(
        "Sweep",
        snapshot.get(
            "sweep_score",
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
                "Factor": "Buy Pressure",
                "Score": snapshot.get(
                    "buy_pressure",
                    0,
                ),
            },
            {
                "Factor": "Sell Pressure",
                "Score": snapshot.get(
                    "sell_pressure",
                    0,
                ),
            },
            {
                "Factor": "Imbalance",
                "Score": snapshot.get(
                    "imbalance_score",
                    0,
                ),
            },
            {
                "Factor": "Absorption",
                "Score": snapshot.get(
                    "absorption_score",
                    0,
                ),
            },
            {
                "Factor": "Sweep",
                "Score": snapshot.get(
                    "sweep_score",
                    0,
                ),
            },
            {
                "Factor": "Liquidity",
                "Score": snapshot.get(
                    "liquidity_score",
                    0,
                ),
            },
            {
                "Factor": "Confidence",
                "Score": snapshot.get(
                    "confidence_score",
                    0,
                ),
            },
        ]
    )

    fig = px.bar(
        factor_df,
        x="Factor",
        y="Score",
        title=f"{pair} Order Flow Factors",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    st.json(snapshot)


# ============================================================
# Rankings
# ============================================================

def render_rankings(
    engine: ForexOrderFlowEngine,
) -> None:

    st.subheader(
        "Order Flow Rankings"
    )

    col1, col2 = st.columns(2)

    direction = col1.selectbox(
        "Direction",
        [
            "BULLISH",
            "BEARISH",
        ],
        key="flow_ranking_direction",
    )

    limit = col2.slider(
        "Ranking Size",
        min_value=5,
        max_value=50,
        value=20,
        key="flow_ranking_limit",
    )

    if st.button(
        "Generate Rankings",
        use_container_width=True,
        key="flow_ranking_button",
    ):

        ranked = engine.rank_flow(
            direction=direction,
            limit=limit,
        )

        st.session_state[
            "flow_rankings"
        ] = [
            x.to_dict()
            for x in ranked
        ]

    ranking_df = _df(
        st.session_state.get(
            "flow_rankings",
            [],
        )
    )

    _grid(
        ranking_df,
        "flow_rankings_grid",
    )

    if (
        not ranking_df.empty
        and "pair" in ranking_df.columns
    ):

        fig = px.bar(
            ranking_df,
            x="pair",
            y="imbalance_score",
            color="flow_direction",
            title="Order Flow Ranking",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )


# ============================================================
# Analytics
# ============================================================

def render_analytics(
    engine: ForexOrderFlowEngine,
) -> None:

    st.subheader(
        "Order Flow Analytics"
    )

    rows = engine.load_snapshots(
        direction="ALL",
        signal="ALL",
        limit=5000,
    )

    df = _df(rows)

    if df.empty:
        st.info(
            "No order flow snapshots available."
        )
        return

    if {
        "flow_direction"
    }.issubset(df.columns):

        direction_df = (
            df.groupby(
                "flow_direction"
            )
            .size()
            .reset_index(
                name="count"
            )
        )

        fig = px.pie(
            direction_df,
            names="flow_direction",
            values="count",
            title="Flow Direction Distribution",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    if {
        "imbalance_score",
        "confidence_score",
    }.issubset(df.columns):

        fig = px.scatter(
            df,
            x="imbalance_score",
            y="confidence_score",
            color="flow_direction",
            size="liquidity_score"
            if "liquidity_score"
            in df.columns
            else None,
            hover_name="pair"
            if "pair"
            in df.columns
            else None,
            title="Imbalance vs Confidence",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    if {
        "pair",
        "absorption_score",
    }.issubset(df.columns):

        fig = px.bar(
            df.sort_values(
                "absorption_score",
                ascending=False,
            ).head(20),
            x="pair",
            y="absorption_score",
            color="flow_direction",
            title="Absorption Ranking",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    if {
        "pair",
        "sweep_score",
    }.issubset(df.columns):

        fig = px.bar(
            df.sort_values(
                "sweep_score",
                ascending=False,
            ).head(20),
            x="pair",
            y="sweep_score",
            color="flow_direction",
            title="Sweep Ranking",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    _grid(
        df,
        "flow_analytics_grid",
    )


# ============================================================
# History
# ============================================================

def render_history(
    engine: ForexOrderFlowEngine,
) -> None:

    st.subheader(
        "Order Flow Scan History"
    )

    if st.button(
        "Load History",
        key="flow_history_button",
    ):

        rows = engine.load_scans(
            limit=1000,
        )

        st.session_state[
            "flow_history"
        ] = rows

    history_df = _df(
        st.session_state.get(
            "flow_history",
            [],
        )
    )

    if history_df.empty:
        st.info(
            "No order flow history available."
        )
        return

    _grid(
        history_df,
        "flow_history_grid",
    )

    if (
        "created_at"
        in history_df.columns
        and "avg_imbalance_score"
        in history_df.columns
    ):

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=history_df[
                    "created_at"
                ],
                y=history_df[
                    "avg_imbalance_score"
                ],
                mode="lines+markers",
                name="Imbalance",
            )
        )

        fig.update_layout(
            title="Average Imbalance Trend",
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

    render_forex_order_flow_dashboard(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )