# modules/forex/forex_execution_quality_dashboard.py

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
    from modules.forex.forex_execution_quality_engine import (
        ForexExecutionQualityEngine,
        get_forex_execution_quality_engine,
    )
except Exception:
    from forex_execution_quality_engine import (
        ForexExecutionQualityEngine,
        get_forex_execution_quality_engine,
    )


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
        st.info("No execution quality data available.")
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
# Charts
# ============================================================

def _execution_score_chart(df: pd.DataFrame) -> None:
    if df.empty:
        return

    required = ["pair", "execution_score"]

    if not all(c in df.columns for c in required):
        return

    chart_df = (
        df.groupby("pair")["execution_score"]
        .mean()
        .reset_index()
        .sort_values(
            "execution_score",
            ascending=False,
        )
    )

    fig = px.bar(
        chart_df,
        x="pair",
        y="execution_score",
        title="Execution Score by Pair",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


def _slippage_chart(df: pd.DataFrame) -> None:
    if df.empty:
        return

    required = ["pair", "slippage_bps"]

    if not all(c in df.columns for c in required):
        return

    chart_df = (
        df.groupby("pair")["slippage_bps"]
        .mean()
        .reset_index()
    )

    fig = px.bar(
        chart_df,
        x="pair",
        y="slippage_bps",
        title="Average Slippage (bps)",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


def _spread_chart(df: pd.DataFrame) -> None:
    if df.empty:
        return

    required = ["pair", "spread_bps"]

    if not all(c in df.columns for c in required):
        return

    chart_df = (
        df.groupby("pair")["spread_bps"]
        .mean()
        .reset_index()
    )

    fig = px.bar(
        chart_df,
        x="pair",
        y="spread_bps",
        title="Average Spread (bps)",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


def _latency_chart(df: pd.DataFrame) -> None:
    if df.empty:
        return

    required = ["pair", "execution_latency_ms"]

    if not all(c in df.columns for c in required):
        return

    chart_df = (
        df.groupby("pair")["execution_latency_ms"]
        .mean()
        .reset_index()
    )

    fig = px.bar(
        chart_df,
        x="pair",
        y="execution_latency_ms",
        title="Execution Latency (ms)",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


def _fill_ratio_chart(df: pd.DataFrame) -> None:
    if df.empty:
        return

    required = ["pair", "fill_ratio"]

    if not all(c in df.columns for c in required):
        return

    chart_df = (
        df.groupby("pair")["fill_ratio"]
        .mean()
        .reset_index()
    )

    fig = px.bar(
        chart_df,
        x="pair",
        y="fill_ratio",
        title="Average Fill Ratio",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


def _scatter_chart(df: pd.DataFrame) -> None:
    required = [
        "slippage_bps",
        "execution_score",
    ]

    if df.empty:
        return

    if not all(c in df.columns for c in required):
        return

    fig = px.scatter(
        df,
        x="slippage_bps",
        y="execution_score",
        color="pair"
        if "pair" in df.columns
        else None,
        size="fill_quality_score"
        if "fill_quality_score" in df.columns
        else None,
        hover_name="pair"
        if "pair" in df.columns
        else None,
        title="Execution Quality vs Slippage",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


# ============================================================
# Main Dashboard
# ============================================================

def render_forex_execution_quality_dashboard(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    execution_quality_engine: Optional[
        ForexExecutionQualityEngine
    ] = None,
) -> None:

    engine = execution_quality_engine or (
        get_forex_execution_quality_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )
    )

    st.title("Forex Execution Quality Center")

    st.caption(
        "Institutional Forex Execution Analytics"
    )

    workspace = st.radio(
        "Execution Quality Workspace",
        [
            "Scanner",
            "Records",
            "Analytics",
            "History",
        ],
        horizontal=True,
        key="forex_execution_quality_workspace",
    )

    if workspace == "Scanner":
        render_scanner(engine)

    elif workspace == "Records":
        render_records(engine)

    elif workspace == "Analytics":
        render_analytics(engine)

    elif workspace == "History":
        render_history(engine)


# ============================================================
# Scanner
# ============================================================

def render_scanner(
    engine: ForexExecutionQualityEngine,
) -> None:

    st.subheader(
        "Execution Quality Scanner"
    )

    col1, col2, col3 = st.columns(3)

    account_id = col1.text_input(
        "Forex Account ID",
        value="",
        key="fx_exec_quality_account",
    )

    status = col2.selectbox(
        "Order Status",
        [
            "ALL",
            "FILLED",
            "PARTIALLY_FILLED",
            "PENDING",
            "CANCELLED",
            "REJECTED",
        ],
        key="fx_exec_quality_status",
    )

    limit = col3.number_input(
        "Scan Limit",
        min_value=10,
        max_value=5000,
        value=250,
        step=10,
        key="fx_exec_quality_limit",
    )

    if st.button(
        "Run Execution Quality Scan",
        key="fx_exec_quality_scan_btn",
        use_container_width=True,
    ):
        with st.spinner(
            "Analyzing execution quality..."
        ):
            summary = engine.run_quality_scan(
                account_id=account_id or None,
                status=status,
                limit=int(limit),
                save=True,
            )

            st.session_state[
                "forex_execution_quality_summary"
            ] = summary.to_dict()

    summary = st.session_state.get(
        "forex_execution_quality_summary"
    )

    if not summary:
        st.info(
            "Run an execution quality scan."
        )
        return

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Records",
        summary.get(
            "total_records",
            0,
        ),
    )

    c2.metric(
        "Execution Score",
        summary.get(
            "avg_execution_score",
            0,
        ),
    )

    c3.metric(
        "Slippage (bps)",
        summary.get(
            "avg_slippage_bps",
            0,
        ),
    )

    c4.metric(
        "Latency (ms)",
        summary.get(
            "avg_execution_latency_ms",
            0,
        ),
    )

    c5.metric(
        "Fill Ratio",
        summary.get(
            "avg_fill_ratio",
            0,
        ),
    )

    st.divider()

    records = summary.get(
        "records",
        [],
    )

    df = _df(records)

    _grid(
        df,
        "fx_execution_quality_scan_grid",
    )


# ============================================================
# Records
# ============================================================

def render_records(
    engine: ForexExecutionQualityEngine,
) -> None:

    st.subheader(
        "Execution Quality Records"
    )

    col1, col2, col3 = st.columns(3)

    pair = col1.text_input(
        "Pair Filter",
        value="",
        key="fx_exec_pair_filter",
    )

    account_id = col2.text_input(
        "Account Filter",
        value="",
        key="fx_exec_account_filter",
    )

    status = col3.selectbox(
        "Status Filter",
        [
            "ALL",
            "FILLED",
            "PARTIALLY_FILLED",
            "PENDING",
            "CANCELLED",
            "REJECTED",
        ],
        key="fx_exec_status_filter",
    )

    if st.button(
        "Load Records",
        key="fx_exec_load_records_btn",
    ):
        rows = engine.load_quality_records(
            pair=pair or None,
            account_id=account_id or None,
            status=status,
            limit=5000,
        )

        st.session_state[
            "fx_exec_records"
        ] = rows

    rows = st.session_state.get(
        "fx_exec_records",
        [],
    )

    df = _df(rows)

    _grid(
        df,
        "fx_exec_records_grid",
    )


# ============================================================
# Analytics
# ============================================================

def render_analytics(
    engine: ForexExecutionQualityEngine,
) -> None:

    st.subheader(
        "Execution Quality Analytics"
    )

    rows = engine.load_quality_records(
        status="ALL",
        limit=5000,
    )

    df = _df(rows)

    if df.empty:
        st.info(
            "No execution quality records available."
        )
        return

    col1, col2 = st.columns(2)

    with col1:
        _execution_score_chart(df)

    with col2:
        _slippage_chart(df)

    col3, col4 = st.columns(2)

    with col3:
        _spread_chart(df)

    with col4:
        _latency_chart(df)

    st.divider()

    _fill_ratio_chart(df)

    st.divider()

    _scatter_chart(df)

    st.divider()

    st.subheader(
        "Top Execution Quality Rankings"
    )

    ranking_df = df.sort_values(
        by=[
            "execution_score",
            "fill_quality_score",
            "price_improvement_score",
        ],
        ascending=False,
    )

    _grid(
        ranking_df.head(100),
        "fx_exec_rankings_grid",
    )


# ============================================================
# History
# ============================================================

def render_history(
    engine: ForexExecutionQualityEngine,
) -> None:

    st.subheader(
        "Execution Quality History"
    )

    account_id = st.text_input(
        "Account History Filter",
        value="",
        key="fx_exec_history_account",
    )

    if st.button(
        "Load History",
        key="fx_exec_load_history_btn",
    ):
        rows = engine.load_summary_history(
            account_id=account_id or None,
            limit=1000,
        )

        st.session_state[
            "fx_exec_history"
        ] = rows

    rows = st.session_state.get(
        "fx_exec_history",
        [],
    )

    df = _df(rows)

    if df.empty:
        st.info(
            "No history available."
        )
        return

    _grid(
        df,
        "fx_exec_history_grid",
    )

    if (
        "created_at" in df.columns
        and "avg_execution_score"
        in df.columns
    ):
        fig = px.line(
            df,
            x="created_at",
            y="avg_execution_score",
            title="Execution Score Trend",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    if (
        "created_at" in df.columns
        and "avg_slippage_bps"
        in df.columns
    ):
        fig = px.line(
            df,
            x="created_at",
            y="avg_slippage_bps",
            title="Slippage Trend",
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
    execution_quality_engine: Optional[
        ForexExecutionQualityEngine
    ] = None,
) -> None:
    render_forex_execution_quality_dashboard(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
        execution_quality_engine=execution_quality_engine,
    )