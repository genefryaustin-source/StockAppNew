# modules/forex/forex_dealer_positioning_dashboard.py

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

    from modules.forex.forex_dealer_positioning_engine import (
        ForexDealerPositioningEngine,
        get_forex_dealer_positioning_engine,
    )

except Exception:

    from forex_service import (
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )

    from forex_dealer_positioning_engine import (
        ForexDealerPositioningEngine,
        get_forex_dealer_positioning_engine,
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
    height: int = 600,
) -> None:

    if df.empty:
        st.info("No dealer positioning data available.")
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
# Main Dashboard
# ============================================================

def render_forex_dealer_positioning_dashboard(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    engine: Optional[
        ForexDealerPositioningEngine
    ] = None,
) -> None:

    engine = (
        engine
        or get_forex_dealer_positioning_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )
    )

    st.title(
        "Forex Dealer Positioning Dashboard"
    )

    st.caption(
        "Dealer Inventory • Hedge Flow • Positioning Pressure • Market-Maker Bias"
    )

    workspace = st.radio(
        "Dealer Positioning Workspace",
        [
            "Scanner",
            "Pair Analysis",
            "Positioning Matrix",
            "Dealer Heatmap",
            "History",
        ],
        horizontal=True,
        key="dealer_positioning_workspace",
    )

    if workspace == "Scanner":
        render_scanner(engine)

    elif workspace == "Pair Analysis":
        render_pair_analysis(engine)

    elif workspace == "Positioning Matrix":
        render_positioning_matrix(engine)

    elif workspace == "Dealer Heatmap":
        render_heatmap(engine)

    elif workspace == "History":
        render_history(engine)


# ============================================================
# Scanner
# ============================================================

def render_scanner(
    engine: ForexDealerPositioningEngine,
) -> None:

    st.subheader(
        "Institutional Dealer Positioning Scanner"
    )

    col1, col2 = st.columns(2)

    pair_group = col1.selectbox(
        "Pair Universe",
        [
            "Major Pairs",
            "Cross Pairs",
            "All Pairs",
        ],
        key="dealer_position_pair_group",
    )

    save_scan = col2.checkbox(
        "Save Scan",
        value=True,
        key="dealer_position_save_scan",
    )

    if pair_group == "Major Pairs":
        pairs = MAJOR_PAIRS

    elif pair_group == "Cross Pairs":
        pairs = CROSS_PAIRS

    else:
        pairs = DEFAULT_PAIRS

    if st.button(
        "Run Dealer Positioning Scan",
        use_container_width=True,
        key="dealer_position_scan_button",
    ):

        with st.spinner(
            "Analyzing dealer inventory positioning..."
        ):

            scan = engine.scan_pairs(
                pairs=pairs,
                save=save_scan,
            )

            st.session_state[
                "dealer_position_scan"
            ] = scan.to_dict()

    scan = st.session_state.get(
        "dealer_position_scan"
    )

    if not scan:
        st.info(
            "Run a dealer positioning scan."
        )
        return

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Pairs",
        scan.get("pair_count", 0),
    )

    c2.metric(
        "Long Bias",
        scan.get("bullish_count", 0),
    )

    c3.metric(
        "Short Bias",
        scan.get("bearish_count", 0),
    )

    c4.metric(
        "Avg Positioning",
        scan.get(
            "average_positioning",
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
            "dealer_bias",
            "positioning_signal",
            "dealer_net_positioning",
            "positioning_conviction",
            "positioning_percentile",
            "inventory_pressure",
            "hedge_pressure",
            "liquidity_pressure",
            "confidence_score",
        ]
        if c in df.columns
    ]

    _grid(
        df[display_cols]
        if not df.empty
        else df,
        "dealer_position_scan_grid",
    )


# ============================================================
# Pair Analysis
# ============================================================

def render_pair_analysis(
    engine: ForexDealerPositioningEngine,
) -> None:

    st.subheader(
        "Dealer Position Analysis"
    )

    pair = st.text_input(
        "Currency Pair",
        value="EUR/USD",
        key="dealer_pair_analysis",
    )

    if st.button(
        "Analyze Dealer Positioning",
        use_container_width=True,
        key="dealer_pair_button",
    ):

        snapshot = engine.analyze_pair(
            pair,
            save=False,
        )

        st.session_state[
            "dealer_position_snapshot"
        ] = snapshot.to_dict()

    snapshot = st.session_state.get(
        "dealer_position_snapshot"
    )

    if not snapshot:
        st.info(
            "Analyze a currency pair."
        )
        return

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Long Score",
        snapshot.get(
            "dealer_long_score",
            0,
        ),
    )

    c2.metric(
        "Short Score",
        snapshot.get(
            "dealer_short_score",
            0,
        ),
    )

    c3.metric(
        "Net Position",
        snapshot.get(
            "dealer_net_positioning",
            0,
        ),
    )

    c4.metric(
        "Conviction",
        snapshot.get(
            "positioning_conviction",
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
                "Factor": "Long Score",
                "Value": snapshot.get(
                    "dealer_long_score",
                    0,
                ),
            },
            {
                "Factor": "Short Score",
                "Value": snapshot.get(
                    "dealer_short_score",
                    0,
                ),
            },
            {
                "Factor": "Inventory Pressure",
                "Value": snapshot.get(
                    "inventory_pressure",
                    0,
                ),
            },
            {
                "Factor": "Hedge Pressure",
                "Value": snapshot.get(
                    "hedge_pressure",
                    0,
                ),
            },
            {
                "Factor": "Liquidity Pressure",
                "Value": snapshot.get(
                    "liquidity_pressure",
                    0,
                ),
            },
            {
                "Factor": "Conviction",
                "Value": snapshot.get(
                    "positioning_conviction",
                    0,
                ),
            },
        ]
    )

    fig = px.bar(
        factor_df,
        x="Factor",
        y="Value",
        title=f"{pair} Dealer Positioning",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    st.json(snapshot)


# ============================================================
# Positioning Matrix
# ============================================================

def render_positioning_matrix(
    engine: ForexDealerPositioningEngine,
) -> None:

    st.subheader(
        "Dealer Positioning Matrix"
    )

    rows = engine.load_snapshots(
        limit=5000,
    )

    df = _df(rows)

    if df.empty:
        st.info(
            "No dealer positioning history available."
        )
        return

    if {
        "dealer_net_positioning",
        "positioning_conviction",
    }.issubset(df.columns):

        fig = px.scatter(
            df,
            x="dealer_net_positioning",
            y="positioning_conviction",
            color="dealer_bias",
            size="confidence_score",
            hover_name="pair",
            title="Dealer Positioning Matrix",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    _grid(
        df,
        "dealer_position_matrix_grid",
    )


# ============================================================
# Heatmap
# ============================================================

def render_heatmap(
    engine: ForexDealerPositioningEngine,
) -> None:

    st.subheader(
        "Dealer Positioning Heatmap"
    )

    rows = engine.load_snapshots(
        limit=5000,
    )

    df = _df(rows)

    if df.empty:
        st.info(
            "No positioning data available."
        )
        return

    if not {
        "pair",
        "dealer_net_positioning",
    }.issubset(df.columns):
        return

    heatmap_df = (
        df.groupby("pair")
        .agg(
            {
                "dealer_net_positioning": "mean",
                "positioning_conviction": "mean",
            }
        )
        .reset_index()
    )

    fig = px.bar(
        heatmap_df.sort_values(
            "dealer_net_positioning",
            ascending=False,
        ),
        x="pair",
        y="dealer_net_positioning",
        color="positioning_conviction",
        title="Dealer Net Positioning",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    fig2 = px.bar(
        heatmap_df.sort_values(
            "positioning_conviction",
            ascending=False,
        ),
        x="pair",
        y="positioning_conviction",
        color="dealer_net_positioning",
        title="Dealer Conviction Ranking",
    )

    st.plotly_chart(
        fig2,
        use_container_width=True,
    )


# ============================================================
# History
# ============================================================

def render_history(
    engine: ForexDealerPositioningEngine,
) -> None:

    st.subheader(
        "Dealer Position History"
    )

    pair = st.text_input(
        "History Pair Filter",
        value="",
        key="dealer_position_history_pair",
    )

    rows = engine.load_snapshots(
        pair=pair if pair else None,
        limit=5000,
    )

    df = _df(rows)

    if df.empty:
        st.info(
            "No positioning history found."
        )
        return

    _grid(
        df,
        "dealer_position_history_grid",
    )

    if {
        "created_at",
        "dealer_net_positioning",
    }.issubset(df.columns):

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=df["created_at"],
                y=df[
                    "dealer_net_positioning"
                ],
                mode="lines+markers",
                name="Net Positioning",
            )
        )

        fig.update_layout(
            title="Dealer Net Positioning Trend"
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

    render_forex_dealer_positioning_dashboard(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )