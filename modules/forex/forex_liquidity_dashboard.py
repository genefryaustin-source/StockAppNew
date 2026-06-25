# modules/forex/forex_liquidity_dashboard.py

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from typing import Any, Dict, List, Optional

try:
    from st_aggrid import AgGrid, GridOptionsBuilder
    HAS_AGGRID = True
except Exception:
    HAS_AGGRID = False

try:
    from modules.forex.forex_liquidity_engine import (
        ForexLiquidityEngine,
        get_forex_liquidity_engine,
    )
    from modules.forex.forex_service import MAJOR_PAIRS, CROSS_PAIRS
except Exception:
    from forex_liquidity_engine import (
        ForexLiquidityEngine,
        get_forex_liquidity_engine,
    )
    from forex_service import MAJOR_PAIRS, CROSS_PAIRS


DEFAULT_PAIRS = MAJOR_PAIRS + CROSS_PAIRS


def _df(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _grid(df: pd.DataFrame, key: str, height: int = 600) -> None:
    if df.empty:
        st.info("No liquidity data available.")
        return

    if HAS_AGGRID:
        builder = GridOptionsBuilder.from_dataframe(df)
        builder.configure_default_column(sortable=True, filter=True, resizable=True)
        builder.configure_pagination(enabled=True, paginationPageSize=25)
        builder.configure_side_bar()
        AgGrid(
            df,
            gridOptions=builder.build(),
            fit_columns_on_grid_load=False,
            height=height,
            key=key,
        )
    else:
        st.dataframe(df, use_container_width=True, hide_index=True, height=height)


def _tier_chart(df: pd.DataFrame) -> None:
    if df.empty or "liquidity_tier" not in df.columns:
        return

    chart_df = (
        df.groupby("liquidity_tier")
        .size()
        .reset_index(name="count")
    )

    fig = px.pie(
        chart_df,
        names="liquidity_tier",
        values="count",
        title="Liquidity Tier Distribution",
    )
    st.plotly_chart(fig, use_container_width=True)


def _liquidity_score_chart(df: pd.DataFrame) -> None:
    if df.empty or "pair" not in df.columns or "liquidity_score" not in df.columns:
        return

    chart_df = (
        df.sort_values("liquidity_score", ascending=False)
        .head(30)
    )

    fig = px.bar(
        chart_df,
        x="pair",
        y="liquidity_score",
        color="liquidity_tier" if "liquidity_tier" in chart_df.columns else None,
        title="Liquidity Score by Pair",
    )
    st.plotly_chart(fig, use_container_width=True)


def _tradability_score_chart(df: pd.DataFrame) -> None:
    if df.empty or "pair" not in df.columns or "tradability_score" not in df.columns:
        return

    chart_df = (
        df.sort_values("tradability_score", ascending=False)
        .head(30)
    )

    fig = px.bar(
        chart_df,
        x="pair",
        y="tradability_score",
        color="liquidity_tier" if "liquidity_tier" in chart_df.columns else None,
        title="Tradability Score by Pair",
    )
    st.plotly_chart(fig, use_container_width=True)


def _spread_chart(df: pd.DataFrame) -> None:
    if df.empty or "pair" not in df.columns or "spread_bps" not in df.columns:
        return

    chart_df = (
        df.sort_values("spread_bps", ascending=True)
        .head(30)
    )

    fig = px.bar(
        chart_df,
        x="pair",
        y="spread_bps",
        color="liquidity_tier" if "liquidity_tier" in chart_df.columns else None,
        title="Spread bps by Pair",
    )
    st.plotly_chart(fig, use_container_width=True)


def _depth_volume_chart(df: pd.DataFrame) -> None:
    required = {"estimated_depth_score", "volume_proxy", "pair", "tradability_score"}
    if df.empty or not required.issubset(set(df.columns)):
        return

    fig = px.scatter(
        df,
        x="estimated_depth_score",
        y="volume_proxy",
        size="tradability_score",
        color="liquidity_tier" if "liquidity_tier" in df.columns else None,
        hover_name="pair",
        title="Depth Score vs Volume Proxy",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_forex_liquidity_dashboard(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    liquidity_engine: Optional[ForexLiquidityEngine] = None,
) -> None:
    engine = liquidity_engine or get_forex_liquidity_engine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )

    st.title("Forex Liquidity Center")
    st.caption("Bid/ask spread, relative spread, depth proxy, volume proxy, liquidity score, and tradability score.")

    workspace = st.radio(
        "Liquidity Workspace",
        [
            "Scanner",
            "Pair Analysis",
            "Snapshots",
            "Analytics",
            "History",
        ],
        horizontal=True,
        key="forex_liquidity_workspace",
    )

    if workspace == "Scanner":
        render_scanner(engine)

    elif workspace == "Pair Analysis":
        render_pair_analysis(engine)

    elif workspace == "Snapshots":
        render_snapshots(engine)

    elif workspace == "Analytics":
        render_analytics(engine)

    elif workspace == "History":
        render_history(engine)


def render_scanner(engine: ForexLiquidityEngine) -> None:
    st.subheader("Forex Liquidity Scanner")

    col1, col2, col3 = st.columns(3)

    pair_group = col1.selectbox(
        "Pair Group",
        ["All Watchlist", "Major Pairs", "Cross Pairs", "Custom"],
        key="fx_liquidity_pair_group",
    )

    min_tradability = col2.slider(
        "Minimum Tradability",
        min_value=0,
        max_value=100,
        value=0,
        step=1,
        key="fx_liquidity_min_tradability",
    )

    save_results = col3.checkbox(
        "Save Results",
        value=True,
        key="fx_liquidity_save_results",
    )

    if pair_group == "Major Pairs":
        selected_pairs = MAJOR_PAIRS
    elif pair_group == "Cross Pairs":
        selected_pairs = CROSS_PAIRS
    elif pair_group == "Custom":
        custom_pairs = st.text_area(
            "Custom Pairs",
            value="EUR/USD\nGBP/USD\nUSD/JPY",
            key="fx_liquidity_custom_pairs",
        )
        selected_pairs = [
            item.strip().upper()
            for item in custom_pairs.splitlines()
            if item.strip()
        ]
    else:
        selected_pairs = DEFAULT_PAIRS

    if st.button(
        "Run Liquidity Scan",
        key="fx_liquidity_scan_btn",
        use_container_width=True,
    ):
        with st.spinner("Scanning Forex liquidity..."):
            scan = engine.scan_pairs(
                pairs=selected_pairs,
                min_tradability_score=float(min_tradability),
                save=bool(save_results),
            )
            st.session_state["fx_liquidity_scan"] = scan.to_dict()

    scan = st.session_state.get("fx_liquidity_scan")

    if not scan:
        st.info("Run a liquidity scan.")
        return

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric("Pairs", scan.get("pair_count", 0))
    c2.metric("Avg Liquidity", scan.get("avg_liquidity_score", 0))
    c3.metric("Avg Tradability", scan.get("avg_tradability_score", 0))
    c4.metric("Best Pair", scan.get("best_pair") or "-")
    c5.metric("Worst Pair", scan.get("worst_pair") or "-")

    st.divider()

    df = _df(scan.get("snapshots", []))
    _grid(df, "fx_liquidity_scan_grid")


def render_pair_analysis(engine: ForexLiquidityEngine) -> None:
    st.subheader("Pair Liquidity Analysis")

    col1, col2 = st.columns(2)

    pair = col1.text_input(
        "Analysis Pair",
        value="EUR/USD",
        key="fx_liquidity_pair_analysis_pair",
    )

    save_result = col2.checkbox(
        "Save Pair Analysis",
        value=True,
        key="fx_liquidity_pair_save",
    )

    if st.button(
        "Analyze Pair Liquidity",
        key="fx_liquidity_pair_btn",
        use_container_width=True,
    ):
        with st.spinner("Analyzing pair liquidity..."):
            snapshot = engine.analyze_pair(
                pair,
                save=bool(save_result),
            )
            st.session_state["fx_liquidity_pair_snapshot"] = snapshot.to_dict()

    snapshot = st.session_state.get("fx_liquidity_pair_snapshot")

    if not snapshot:
        st.info("Analyze a pair to view liquidity detail.")
        return

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric("Pair", snapshot.get("pair"))
    c2.metric("Liquidity", snapshot.get("liquidity_score"))
    c3.metric("Tradability", snapshot.get("tradability_score"))
    c4.metric("Spread bps", snapshot.get("spread_bps"))
    c5.metric("Tier", snapshot.get("liquidity_tier"))

    if snapshot.get("notes"):
        st.info(snapshot.get("notes"))

    st.divider()

    score_df = pd.DataFrame(
        [
            {"metric": "Liquidity", "score": snapshot.get("liquidity_score", 0)},
            {"metric": "Tradability", "score": snapshot.get("tradability_score", 0)},
            {"metric": "Depth", "score": snapshot.get("estimated_depth_score", 0)},
            {"metric": "Volume Proxy", "score": snapshot.get("volume_proxy", 0)},
            {"metric": "Volatility Penalty", "score": snapshot.get("volatility_penalty", 0)},
        ]
    )

    fig = px.bar(
        score_df,
        x="metric",
        y="score",
        title="Liquidity Score Breakdown",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.json(snapshot)


def render_snapshots(engine: ForexLiquidityEngine) -> None:
    st.subheader("Liquidity Snapshots")

    col1, col2, col3 = st.columns(3)

    pair = col1.text_input(
        "Pair Filter",
        value="",
        key="fx_liquidity_snapshot_pair",
    )

    tier = col2.selectbox(
        "Liquidity Tier",
        ["ALL", "EXCELLENT", "GOOD", "AVERAGE", "WEAK", "POOR"],
        key="fx_liquidity_snapshot_tier",
    )

    limit = col3.number_input(
        "Snapshot Limit",
        min_value=10,
        max_value=5000,
        value=500,
        step=10,
        key="fx_liquidity_snapshot_limit",
    )

    if st.button(
        "Load Liquidity Snapshots",
        key="fx_liquidity_load_snapshots",
    ):
        rows = engine.load_snapshots(
            pair=pair or None,
            liquidity_tier=tier,
            limit=int(limit),
        )
        st.session_state["fx_liquidity_snapshots"] = rows

    rows = st.session_state.get("fx_liquidity_snapshots", [])
    df = _df(rows)

    _grid(df, "fx_liquidity_snapshots_grid")


def render_analytics(engine: ForexLiquidityEngine) -> None:
    st.subheader("Liquidity Analytics")

    rows = engine.load_snapshots(
        liquidity_tier="ALL",
        limit=5000,
    )

    df = _df(rows)

    if df.empty:
        st.info("No liquidity snapshots available.")
        return

    c1, c2 = st.columns(2)

    with c1:
        _tier_chart(df)

    with c2:
        _spread_chart(df)

    c3, c4 = st.columns(2)

    with c3:
        _liquidity_score_chart(df)

    with c4:
        _tradability_score_chart(df)

    st.divider()

    _depth_volume_chart(df)

    st.divider()

    st.subheader("Best Tradable Pairs")

    ranking_df = df.sort_values(
        by=[
            "tradability_score",
            "liquidity_score",
            "spread_bps",
        ],
        ascending=[False, False, True],
    )

    _grid(
        ranking_df.head(100),
        "fx_liquidity_rankings_grid",
    )


def render_history(engine: ForexLiquidityEngine) -> None:
    st.subheader("Liquidity Scan History")

    if st.button(
        "Load Liquidity Scan History",
        key="fx_liquidity_history_btn",
    ):
        rows = engine.load_scans(limit=1000)
        st.session_state["fx_liquidity_history"] = rows

    rows = st.session_state.get("fx_liquidity_history", [])
    df = _df(rows)

    if df.empty:
        st.info("No liquidity scan history available.")
        return

    _grid(df, "fx_liquidity_history_grid")

    if "created_at" in df.columns and "avg_liquidity_score" in df.columns:
        fig = px.line(
            df,
            x="created_at",
            y="avg_liquidity_score",
            title="Average Liquidity Score Trend",
        )
        st.plotly_chart(fig, use_container_width=True)

    if "created_at" in df.columns and "avg_tradability_score" in df.columns:
        fig = px.line(
            df,
            x="created_at",
            y="avg_tradability_score",
            title="Average Tradability Score Trend",
        )
        st.plotly_chart(fig, use_container_width=True)


def render(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    liquidity_engine: Optional[ForexLiquidityEngine] = None,
) -> None:
    render_forex_liquidity_dashboard(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
        liquidity_engine=liquidity_engine,
    )