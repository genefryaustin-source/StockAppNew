# modules/forex/forex_dealer_dashboard.py

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

    from modules.forex.forex_liquidity_engine import (
        ForexLiquidityEngine,
        get_forex_liquidity_engine,
    )

    from modules.forex.forex_macro_engine import (
        ForexMacroEngine,
        get_forex_macro_engine,
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

    from forex_liquidity_engine import (
        ForexLiquidityEngine,
        get_forex_liquidity_engine,
    )

    from forex_macro_engine import (
        ForexMacroEngine,
        get_forex_macro_engine,
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
    height: int = 550,
) -> None:

    if df.empty:
        st.info("No data available.")
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

def render_forex_dealer_dashboard(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    order_flow_engine: Optional[
        ForexOrderFlowEngine
    ] = None,
    liquidity_engine: Optional[
        ForexLiquidityEngine
    ] = None,
    macro_engine: Optional[
        ForexMacroEngine
    ] = None,
) -> None:

    order_flow_engine = (
        order_flow_engine
        or get_forex_order_flow_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )
    )

    liquidity_engine = (
        liquidity_engine
        or get_forex_liquidity_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )
    )

    macro_engine = (
        macro_engine
        or get_forex_macro_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )
    )

    st.title("Forex Dealer Dashboard")

    st.caption(
        "Institutional Dealer Intelligence • Flow • Liquidity • Macro • Market Making"
    )

    workspace = st.radio(
        "Dealer Workspace",
        [
            "Dealer Blotter",
            "Flow Monitor",
            "Liquidity Matrix",
            "Macro Overlay",
            "Market Making",
        ],
        horizontal=True,
        key="forex_dealer_workspace",
    )

    if workspace == "Dealer Blotter":
        render_dealer_blotter(
            order_flow_engine
        )

    elif workspace == "Flow Monitor":
        render_flow_monitor(
            order_flow_engine
        )

    elif workspace == "Liquidity Matrix":
        render_liquidity_matrix(
            liquidity_engine
        )

    elif workspace == "Macro Overlay":
        render_macro_overlay(
            macro_engine
        )

    elif workspace == "Market Making":
        render_market_making(
            order_flow_engine,
            liquidity_engine,
        )


# ============================================================
# Dealer Blotter
# ============================================================

def render_dealer_blotter(
    order_flow_engine: ForexOrderFlowEngine,
) -> None:

    st.subheader(
        "Institutional Dealer Blotter"
    )

    pair_group = st.selectbox(
        "Pair Universe",
        [
            "Major Pairs",
            "Cross Pairs",
            "All",
        ],
        key="dealer_pair_group",
    )

    if pair_group == "Major Pairs":
        pairs = MAJOR_PAIRS

    elif pair_group == "Cross Pairs":
        pairs = CROSS_PAIRS

    else:
        pairs = DEFAULT_PAIRS

    if st.button(
        "Refresh Dealer Book",
        key="dealer_refresh_book",
    ):
        scan = order_flow_engine.scan_pairs(
            pairs=pairs,
            save=False,
        )

        st.session_state[
            "dealer_blotter_scan"
        ] = scan.to_dict()

    scan = st.session_state.get(
        "dealer_blotter_scan"
    )

    if not scan:
        st.info(
            "Refresh dealer book."
        )
        return

    df = _df(
        scan.get("snapshots", [])
    )

    if not df.empty:
        display_cols = [
            c
            for c in [
                "pair",
                "price",
                "buy_pressure",
                "sell_pressure",
                "imbalance_score",
                "liquidity_score",
                "flow_direction",
                "flow_signal",
                "confidence_score",
            ]
            if c in df.columns
        ]

        _grid(
            df[display_cols],
            "dealer_blotter_grid",
        )


# ============================================================
# Flow Monitor
# ============================================================

def render_flow_monitor(
    order_flow_engine: ForexOrderFlowEngine,
) -> None:

    st.subheader(
        "Dealer Flow Monitor"
    )

    rows = order_flow_engine.load_snapshots(
        direction="ALL",
        signal="ALL",
        limit=1000,
    )

    df = _df(rows)

    if df.empty:
        st.info(
            "No order-flow snapshots."
        )
        return

    c1, c2 = st.columns(2)

    with c1:

        if {
            "pair",
            "imbalance_score",
        }.issubset(df.columns):

            fig = px.bar(
                df.sort_values(
                    "imbalance_score",
                    ascending=False,
                ).head(20),
                x="pair",
                y="imbalance_score",
                color="flow_direction",
                title="Flow Imbalance",
            )

            st.plotly_chart(
                fig,
                use_container_width=True,
            )

    with c2:

        if {
            "pair",
            "confidence_score",
        }.issubset(df.columns):

            fig = px.bar(
                df.sort_values(
                    "confidence_score",
                    ascending=False,
                ).head(20),
                x="pair",
                y="confidence_score",
                color="flow_direction",
                title="Flow Confidence",
            )

            st.plotly_chart(
                fig,
                use_container_width=True,
            )

    _grid(
        df,
        "dealer_flow_monitor",
    )


# ============================================================
# Liquidity Matrix
# ============================================================

def render_liquidity_matrix(
    liquidity_engine: ForexLiquidityEngine,
) -> None:

    st.subheader(
        "Dealer Liquidity Matrix"
    )

    rows = liquidity_engine.load_snapshots(
        liquidity_tier="ALL",
        limit=5000,
    )

    df = _df(rows)

    if df.empty:
        st.info(
            "No liquidity snapshots."
        )
        return

    if {
        "estimated_depth_score",
        "volume_proxy",
    }.issubset(df.columns):

        fig = px.scatter(
            df,
            x="estimated_depth_score",
            y="volume_proxy",
            size="tradability_score",
            color="liquidity_tier",
            hover_name="pair",
            title="Dealer Liquidity Matrix",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    _grid(
        df,
        "dealer_liquidity_grid",
    )


# ============================================================
# Macro Overlay
# ============================================================

def render_macro_overlay(
    macro_engine: ForexMacroEngine,
) -> None:

    st.subheader(
        "Dealer Macro Overlay"
    )

    rows = macro_engine.load_snapshots(
        direction="ALL",
        recommendation="ALL",
        limit=5000,
    )

    df = _df(rows)

    if df.empty:
        st.info(
            "No macro snapshots."
        )
        return

    if {
        "macro_score",
        "confidence_score",
    }.issubset(df.columns):

        fig = px.scatter(
            df,
            x="macro_score",
            y="confidence_score",
            color="macro_direction",
            hover_name="pair",
            size="yield_signal"
            if "yield_signal"
            in df.columns
            else None,
            title="Macro Conviction Matrix",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    _grid(
        df,
        "dealer_macro_grid",
    )


# ============================================================
# Market Making
# ============================================================

def render_market_making(
    order_flow_engine: ForexOrderFlowEngine,
    liquidity_engine: ForexLiquidityEngine,
) -> None:

    st.subheader(
        "Market Making Analytics"
    )

    flow_rows = order_flow_engine.load_snapshots(
        limit=1000,
    )

    liq_rows = liquidity_engine.load_snapshots(
        liquidity_tier="ALL",
        limit=1000,
    )

    flow_df = _df(flow_rows)
    liq_df = _df(liq_rows)

    if flow_df.empty or liq_df.empty:
        st.info(
            "Market making data unavailable."
        )
        return

    if (
        "pair" in flow_df.columns
        and "pair" in liq_df.columns
    ):
        merged = pd.merge(
            flow_df,
            liq_df,
            on="pair",
            how="inner",
        )

        if not merged.empty:

            merged[
                "dealer_edge"
            ] = (
                merged[
                    "liquidity_score"
                ].fillna(0)
                + merged[
                    "absorption_score"
                ].fillna(0)
                + merged[
                    "confidence_score_x"
                ].fillna(0)
            ) / 3.0

            fig = px.scatter(
                merged,
                x="dealer_edge",
                y="imbalance_score",
                color="flow_direction",
                hover_name="pair",
                title="Dealer Edge Matrix",
            )

            st.plotly_chart(
                fig,
                use_container_width=True,
            )

            ranking = merged.sort_values(
                "dealer_edge",
                ascending=False,
            )

            _grid(
                ranking,
                "dealer_edge_grid",
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

    render_forex_dealer_dashboard(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )