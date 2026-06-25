# modules/forex/forex_recommendation_dashboard.py

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
    from modules.forex.forex_recommendation_engine import (
        ForexRecommendationEngine,
        get_forex_recommendation_engine,
    )
except Exception:
    from forex_recommendation_engine import (
        ForexRecommendationEngine,
        get_forex_recommendation_engine,
    )


# ============================================================
# Helpers
# ============================================================

def _df(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _grid(df: pd.DataFrame, key: str) -> None:
    if df.empty:
        st.info("No recommendation data available.")
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
            height=600,
            key=key,
        )
    else:
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            height=600,
        )


def _recommendation_chart(df: pd.DataFrame) -> None:
    if df.empty or "recommendation" not in df.columns:
        return

    chart_df = (
        df.groupby("recommendation")
        .size()
        .reset_index(name="count")
    )

    fig = px.pie(
        chart_df,
        names="recommendation",
        values="count",
        title="Recommendation Distribution",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


def _confidence_chart(df: pd.DataFrame) -> None:
    if df.empty:
        return

    if "pair" not in df.columns:
        return

    if "confidence_score" not in df.columns:
        return

    fig = px.bar(
        df.head(25),
        x="pair",
        y="confidence_score",
        color="recommendation",
        title="Confidence Score by Pair",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


def _conviction_chart(df: pd.DataFrame) -> None:
    if df.empty:
        return

    if "pair" not in df.columns:
        return

    if "conviction_score" not in df.columns:
        return

    fig = px.bar(
        df.head(25),
        x="pair",
        y="conviction_score",
        color="recommendation",
        title="Conviction Score by Pair",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


def _risk_reward_chart(df: pd.DataFrame) -> None:
    if df.empty:
        return

    if "risk_reward" not in df.columns:
        return

    fig = px.scatter(
        df,
        x="confidence_score",
        y="risk_reward",
        color="recommendation",
        size="conviction_score",
        hover_name="pair",
        title="Confidence vs Risk/Reward",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


# ============================================================
# Main Dashboard
# ============================================================

def render_forex_recommendation_dashboard(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    recommendation_engine: Optional[ForexRecommendationEngine] = None,
) -> None:

    engine = recommendation_engine or get_forex_recommendation_engine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )

    st.title("Forex Recommendation Center")

    st.caption(
        "Institutional Forex Recommendation Intelligence"
    )

    workspace = st.radio(
        "Recommendation Workspace",
        [
            "Scanner",
            "Recommendations",
            "Analytics",
            "History",
        ],
        horizontal=True,
        key="forex_recommendation_workspace",
    )

    if workspace == "Scanner":
        render_scanner(engine)

    elif workspace == "Recommendations":
        render_recommendations(engine)

    elif workspace == "Analytics":
        render_analytics(engine)

    elif workspace == "History":
        render_history(engine)


# ============================================================
# Scanner
# ============================================================

def render_scanner(
    engine: ForexRecommendationEngine,
) -> None:

    st.subheader("Forex Recommendation Scanner")

    col1, col2, col3, col4 = st.columns(4)

    account_id = col1.text_input(
        "Forex Account ID",
        value="",
        key="forex_recommendation_account_id",
    )

    min_confidence = col2.slider(
        "Min Confidence",
        min_value=0,
        max_value=100,
        value=55,
        key="forex_recommendation_min_confidence",
    )

    min_rr = col3.slider(
        "Min Risk/Reward",
        min_value=1.0,
        max_value=5.0,
        value=1.0,
        step=0.1,
        key="forex_recommendation_min_rr",
    )

    limit = col4.number_input(
        "Max Results",
        min_value=5,
        max_value=100,
        value=25,
        key="forex_recommendation_limit",
    )

    if st.button(
        "Run Forex Recommendation Scan",
        key="forex_recommendation_scan_btn",
        use_container_width=True,
    ):
        with st.spinner("Scanning Forex markets..."):

            scan = engine.run_scan(
                account_id=account_id or None,
                min_confidence=float(min_confidence),
                min_risk_reward=float(min_rr),
                limit=int(limit),
                save=True,
            )

            st.session_state["forex_recommendation_scan"] = scan.to_dict()

    scan = st.session_state.get(
        "forex_recommendation_scan",
    )

    if not scan:
        st.info("Run a recommendation scan.")
        return

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Recommendations",
        scan.get("recommendation_count", 0),
    )

    c2.metric(
        "Strong Buy",
        scan.get("strong_buy_count", 0),
    )

    c3.metric(
        "Buy",
        scan.get("buy_count", 0),
    )

    c4.metric(
        "Avg Confidence",
        scan.get("avg_confidence", 0),
    )

    c5.metric(
        "Top Pair",
        scan.get("top_pair") or "-",
    )

    st.divider()

    recommendations = scan.get(
        "recommendations",
        [],
    )

    df = _df(recommendations)

    _grid(
        df,
        "forex_recommendation_scan_grid",
    )


# ============================================================
# Recommendations
# ============================================================

def render_recommendations(
    engine: ForexRecommendationEngine,
) -> None:

    st.subheader("Saved Recommendations")

    col1, col2 = st.columns(2)

    pair = col1.text_input(
        "Pair Filter",
        value="",
        key="forex_rec_pair_filter",
    )

    status = col2.selectbox(
        "Recommendation Status",
        [
            "ALL",
            "ACTIVE",
            "EXECUTED",
        ],
        key="forex_rec_status_filter",
    )

    if st.button(
        "Load Recommendations",
        key="forex_load_recommendations_btn",
    ):
        rows = engine.load_recommendations(
            pair=pair or None,
            status=status,
            limit=500,
        )

        st.session_state["forex_loaded_recommendations"] = rows

    rows = st.session_state.get(
        "forex_loaded_recommendations",
        [],
    )

    df = _df(rows)

    _grid(
        df,
        "forex_loaded_recommendations_grid",
    )


# ============================================================
# Analytics
# ============================================================

def render_analytics(
    engine: ForexRecommendationEngine,
) -> None:

    st.subheader("Recommendation Analytics")

    rows = engine.load_recommendations(
        status="ALL",
        limit=1000,
    )

    df = _df(rows)

    if df.empty:
        st.info("No recommendation data available.")
        return

    c1, c2 = st.columns(2)

    with c1:
        _recommendation_chart(df)

    with c2:
        _risk_reward_chart(df)

    c3, c4 = st.columns(2)

    with c3:
        _confidence_chart(df)

    with c4:
        _conviction_chart(df)

    st.divider()

    st.subheader("Top Ranked Opportunities")

    sort_df = df.sort_values(
        by=[
            "conviction_score",
            "confidence_score",
            "risk_reward",
        ],
        ascending=False,
    )

    _grid(
        sort_df.head(50),
        "forex_recommendation_rankings",
    )


# ============================================================
# History
# ============================================================

def render_history(
    engine: ForexRecommendationEngine,
) -> None:

    st.subheader("Recommendation Scan History")

    if st.button(
        "Load Scan History",
        key="forex_scan_history_btn",
    ):
        rows = engine.load_scans(
            limit=500,
        )

        st.session_state["forex_scan_history"] = rows

    rows = st.session_state.get(
        "forex_scan_history",
        [],
    )

    df = _df(rows)

    if df.empty:
        st.info("No scan history available.")
        return

    _grid(
        df,
        "forex_scan_history_grid",
    )

    if "avg_confidence" in df.columns:

        fig = px.line(
            df.head(100),
            x="created_at",
            y="avg_confidence",
            title="Average Confidence Trend",
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
    recommendation_engine: Optional[ForexRecommendationEngine] = None,
) -> None:
    render_forex_recommendation_dashboard(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
        recommendation_engine=recommendation_engine,
    )