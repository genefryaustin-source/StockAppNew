# modules/forex/forex_attribution_dashboard.py

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
    from modules.forex.forex_attribution_engine import (
        ForexAttributionEngine,
        get_forex_attribution_engine,
    )
except Exception:
    from forex_attribution_engine import (
        ForexAttributionEngine,
        get_forex_attribution_engine,
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
        st.info("No attribution data available.")
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

def _outcome_chart(df: pd.DataFrame) -> None:
    if df.empty:
        return

    if "outcome" not in df.columns:
        return

    chart_df = (
        df.groupby("outcome")
        .size()
        .reset_index(name="count")
    )

    fig = px.pie(
        chart_df,
        names="outcome",
        values="count",
        title="Attribution Outcomes",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


def _pair_performance_chart(df: pd.DataFrame) -> None:
    if df.empty:
        return

    if "pair" not in df.columns:
        return

    if "total_pnl" not in df.columns:
        return

    pair_df = (
        df.groupby("pair")["total_pnl"]
        .sum()
        .reset_index()
        .sort_values(
            "total_pnl",
            ascending=False,
        )
    )

    fig = px.bar(
        pair_df,
        x="pair",
        y="total_pnl",
        title="PnL by Currency Pair",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


def _accuracy_chart(df: pd.DataFrame) -> None:
    if df.empty:
        return

    if "pair" not in df.columns:
        return

    if "accuracy_score" not in df.columns:
        return

    fig = px.bar(
        df.head(50),
        x="pair",
        y="accuracy_score",
        color="outcome",
        title="Recommendation Accuracy",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


def _attribution_chart(df: pd.DataFrame) -> None:
    if df.empty:
        return

    if "pair" not in df.columns:
        return

    if "attribution_score" not in df.columns:
        return

    fig = px.bar(
        df.head(50),
        x="pair",
        y="attribution_score",
        color="recommendation",
        title="Attribution Score",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


def _scatter_chart(df: pd.DataFrame) -> None:
    if df.empty:
        return

    required = [
        "conviction_score",
        "total_pnl",
        "pair",
    ]

    for col in required:
        if col not in df.columns:
            return

    fig = px.scatter(
        df,
        x="conviction_score",
        y="total_pnl",
        color="outcome",
        hover_name="pair",
        size="accuracy_score"
        if "accuracy_score" in df.columns
        else None,
        title="Conviction vs Realized Outcome",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


# ============================================================
# Dashboard
# ============================================================

def render_forex_attribution_dashboard(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    attribution_engine: Optional[ForexAttributionEngine] = None,
) -> None:

    engine = attribution_engine or get_forex_attribution_engine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )

    st.title("Forex Attribution Center")

    st.caption(
        "Recommendation → Order → Trade → PnL Attribution"
    )

    workspace = st.radio(
        "Attribution Workspace",
        [
            "Scanner",
            "Records",
            "Analytics",
            "History",
        ],
        horizontal=True,
        key="forex_attribution_workspace",
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
    engine: ForexAttributionEngine,
) -> None:

    st.subheader("Forex Attribution Scan")

    col1, col2, col3 = st.columns(3)

    account_id = col1.text_input(
        "Forex Account ID",
        value="",
        key="forex_attr_account_id",
    )

    status = col2.selectbox(
        "Recommendation Status",
        [
            "ALL",
            "ACTIVE",
            "EXECUTED",
        ],
        key="forex_attr_status",
    )

    limit = col3.number_input(
        "Scan Limit",
        min_value=10,
        max_value=1000,
        value=250,
        step=10,
        key="forex_attr_limit",
    )

    if st.button(
        "Run Attribution Scan",
        key="forex_attr_scan_btn",
        use_container_width=True,
    ):
        with st.spinner("Running attribution analysis..."):

            summary = engine.run_attribution_scan(
                account_id=account_id or None,
                status=status,
                limit=int(limit),
                save=True,
            )

            st.session_state["forex_attribution_summary"] = (
                summary.to_dict()
            )

    summary = st.session_state.get(
        "forex_attribution_summary",
    )

    if not summary:
        st.info("Run an attribution scan.")
        return

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Records",
        summary.get("total_records", 0),
    )

    c2.metric(
        "Win Rate",
        f"{summary.get('win_rate', 0)}%",
    )

    c3.metric(
        "Total PnL",
        summary.get("total_pnl", 0),
    )

    c4.metric(
        "Avg Attribution",
        summary.get("avg_attribution_score", 0),
    )

    c5.metric(
        "Avg Accuracy",
        summary.get("avg_accuracy_score", 0),
    )

    st.divider()

    records = summary.get(
        "records",
        [],
    )

    df = _df(records)

    _grid(
        df,
        "forex_attr_scan_grid",
    )


# ============================================================
# Records
# ============================================================

def render_records(
    engine: ForexAttributionEngine,
) -> None:

    st.subheader("Attribution Records")

    col1, col2, col3 = st.columns(3)

    pair = col1.text_input(
        "Pair Filter",
        value="",
        key="forex_attr_pair_filter",
    )

    account_id = col2.text_input(
        "Account Filter",
        value="",
        key="forex_attr_account_filter",
    )

    outcome = col3.selectbox(
        "Outcome Filter",
        [
            "ALL",
            "WIN",
            "LOSS",
            "OPEN",
            "OPEN_GAIN",
            "OPEN_LOSS",
            "FLAT",
        ],
        key="forex_attr_outcome_filter",
    )

    if st.button(
        "Load Attribution Records",
        key="forex_attr_records_btn",
    ):
        rows = engine.load_attribution_records(
            pair=pair or None,
            account_id=account_id or None,
            outcome=outcome,
            limit=1000,
        )

        st.session_state["forex_attr_records"] = rows

    rows = st.session_state.get(
        "forex_attr_records",
        [],
    )

    df = _df(rows)

    _grid(
        df,
        "forex_attr_records_grid",
    )


# ============================================================
# Analytics
# ============================================================

def render_analytics(
    engine: ForexAttributionEngine,
) -> None:

    st.subheader("Attribution Analytics")

    rows = engine.load_attribution_records(
        outcome="ALL",
        limit=5000,
    )

    df = _df(rows)

    if df.empty:
        st.info("No attribution records available.")
        return

    col1, col2 = st.columns(2)

    with col1:
        _outcome_chart(df)

    with col2:
        _pair_performance_chart(df)

    col3, col4 = st.columns(2)

    with col3:
        _accuracy_chart(df)

    with col4:
        _attribution_chart(df)

    st.divider()

    _scatter_chart(df)

    st.divider()

    st.subheader("Top Attribution Opportunities")

    ranking_df = df.sort_values(
        by=[
            "attribution_score",
            "accuracy_score",
            "total_pnl",
        ],
        ascending=False,
    )

    _grid(
        ranking_df.head(100),
        "forex_attr_ranking_grid",
    )


# ============================================================
# History
# ============================================================

def render_history(
    engine: ForexAttributionEngine,
) -> None:

    st.subheader("Attribution Snapshot History")

    if st.button(
        "Load Attribution History",
        key="forex_attr_history_btn",
    ):
        rows = engine.load_summary_history(
            limit=1000,
        )

        st.session_state["forex_attr_history"] = rows

    rows = st.session_state.get(
        "forex_attr_history",
        [],
    )

    df = _df(rows)

    if df.empty:
        st.info("No attribution history available.")
        return

    _grid(
        df,
        "forex_attr_history_grid",
    )

    if "created_at" in df.columns and "win_rate" in df.columns:

        fig = px.line(
            df,
            x="created_at",
            y="win_rate",
            title="Win Rate Trend",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    if (
        "created_at" in df.columns
        and "total_pnl" in df.columns
    ):

        fig = px.line(
            df,
            x="created_at",
            y="total_pnl",
            title="Total Attribution PnL Trend",
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
    attribution_engine: Optional[ForexAttributionEngine] = None,
) -> None:
    render_forex_attribution_dashboard(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
        attribution_engine=attribution_engine,
    )