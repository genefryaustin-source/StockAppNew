# modules/forex/forex_macro_dashboard.py

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
    from modules.forex.forex_macro_engine import (
        ForexMacroEngine,
        get_forex_macro_engine,
    )
    from modules.forex.forex_service import (
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )
except Exception:
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
    height: int = 600,
) -> None:
    if df.empty:
        st.info("No macro data available.")
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
# Charts
# ============================================================

def _direction_chart(df: pd.DataFrame) -> None:
    if df.empty or "macro_direction" not in df.columns:
        return

    chart_df = (
        df.groupby("macro_direction")
        .size()
        .reset_index(name="count")
    )

    fig = px.pie(
        chart_df,
        names="macro_direction",
        values="count",
        title="Macro Direction Distribution",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


def _recommendation_chart(df: pd.DataFrame) -> None:
    if df.empty or "macro_recommendation" not in df.columns:
        return

    chart_df = (
        df.groupby("macro_recommendation")
        .size()
        .reset_index(name="count")
    )

    fig = px.bar(
        chart_df,
        x="macro_recommendation",
        y="count",
        title="Macro Recommendations",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


def _macro_score_chart(df: pd.DataFrame) -> None:
    if df.empty:
        return

    required = ["pair", "macro_score"]

    if not all(c in df.columns for c in required):
        return

    chart_df = (
        df.sort_values(
            "macro_score",
            ascending=False,
        )
        .head(30)
    )

    fig = px.bar(
        chart_df,
        x="pair",
        y="macro_score",
        color="macro_direction"
        if "macro_direction" in chart_df.columns
        else None,
        title="Macro Score Ranking",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


def _confidence_chart(df: pd.DataFrame) -> None:
    if df.empty:
        return

    required = ["pair", "confidence_score"]

    if not all(c in df.columns for c in required):
        return

    chart_df = (
        df.sort_values(
            "confidence_score",
            ascending=False,
        )
        .head(30)
    )

    fig = px.bar(
        chart_df,
        x="pair",
        y="confidence_score",
        color="macro_direction"
        if "macro_direction" in chart_df.columns
        else None,
        title="Macro Confidence Score",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


def _rate_differential_chart(df: pd.DataFrame) -> None:
    if df.empty:
        return

    required = ["pair", "rate_differential"]

    if not all(c in df.columns for c in required):
        return

    fig = px.bar(
        df.sort_values(
            "rate_differential",
            ascending=False,
        ),
        x="pair",
        y="rate_differential",
        title="Interest Rate Differential",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


def _growth_differential_chart(df: pd.DataFrame) -> None:
    if df.empty:
        return

    required = ["pair", "growth_differential"]

    if not all(c in df.columns for c in required):
        return

    fig = px.bar(
        df.sort_values(
            "growth_differential",
            ascending=False,
        ),
        x="pair",
        y="growth_differential",
        title="Growth Differential",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


def _macro_scatter(df: pd.DataFrame) -> None:
    required = {
        "macro_score",
        "confidence_score",
    }

    if df.empty:
        return

    if not required.issubset(set(df.columns)):
        return

    fig = px.scatter(
        df,
        x="macro_score",
        y="confidence_score",
        color="macro_direction"
        if "macro_direction" in df.columns
        else None,
        size="yield_signal"
        if "yield_signal" in df.columns
        else None,
        hover_name="pair"
        if "pair" in df.columns
        else None,
        title="Macro Score vs Confidence",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


# ============================================================
# Dashboard
# ============================================================

def render_forex_macro_dashboard(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    macro_engine: Optional[ForexMacroEngine] = None,
) -> None:

    engine = macro_engine or get_forex_macro_engine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )

    st.title("Forex Macro Intelligence Center")

    st.caption(
        "Central Banks • Rates • Inflation • Growth • Risk Regime • Yield Differentials"
    )

    workspace = st.radio(
        "Macro Workspace",
        [
            "Scanner",
            "Pair Analysis",
            "Snapshots",
            "Analytics",
            "History",
        ],
        horizontal=True,
        key="forex_macro_workspace",
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


# ============================================================
# Scanner
# ============================================================

def render_scanner(
    engine: ForexMacroEngine,
) -> None:

    st.subheader("Forex Macro Scanner")

    col1, col2 = st.columns(2)

    pair_group = col1.selectbox(
        "Pair Group",
        [
            "All Watchlist",
            "Major Pairs",
            "Cross Pairs",
            "Custom",
        ],
        key="fx_macro_pair_group",
    )

    save_results = col2.checkbox(
        "Save Results",
        value=True,
        key="fx_macro_save_results",
    )

    if pair_group == "Major Pairs":
        selected_pairs = MAJOR_PAIRS

    elif pair_group == "Cross Pairs":
        selected_pairs = CROSS_PAIRS

    elif pair_group == "Custom":
        custom_pairs = st.text_area(
            "Custom Pairs",
            value="EUR/USD\nGBP/USD\nUSD/JPY",
            key="fx_macro_custom_pairs",
        )

        selected_pairs = [
            p.strip().upper()
            for p in custom_pairs.splitlines()
            if p.strip()
        ]

    else:
        selected_pairs = DEFAULT_PAIRS

    if st.button(
        "Run Macro Scan",
        key="fx_macro_scan_btn",
        use_container_width=True,
    ):
        with st.spinner("Running macro intelligence scan..."):

            scan = engine.scan_pairs(
                pairs=selected_pairs,
                save=save_results,
            )

            st.session_state["fx_macro_scan"] = (
                scan.to_dict()
            )

    scan = st.session_state.get(
        "fx_macro_scan"
    )

    if not scan:
        st.info("Run a macro scan.")
        return

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Pairs",
        scan.get("pair_count", 0),
    )

    c2.metric(
        "Avg Macro",
        scan.get("avg_macro_score", 0),
    )

    c3.metric(
        "Avg Confidence",
        scan.get("avg_confidence_score", 0),
    )

    c4.metric(
        "Bullish",
        scan.get("bullish_count", 0),
    )

    c5.metric(
        "Bearish",
        scan.get("bearish_count", 0),
    )

    st.divider()

    df = _df(
        scan.get("snapshots", [])
    )

    _grid(
        df,
        "fx_macro_scan_grid",
    )


# ============================================================
# Pair Analysis
# ============================================================

def render_pair_analysis(
    engine: ForexMacroEngine,
) -> None:

    st.subheader("Pair Macro Analysis")

    col1, col2 = st.columns(2)

    pair = col1.text_input(
        "Pair",
        value="EUR/USD",
        key="fx_macro_pair_analysis",
    )

    save_result = col2.checkbox(
        "Save Analysis",
        value=True,
        key="fx_macro_pair_save",
    )

    if st.button(
        "Analyze Macro",
        key="fx_macro_pair_btn",
        use_container_width=True,
    ):
        with st.spinner("Analyzing macro drivers..."):

            snapshot = engine.analyze_pair(
                pair,
                save=save_result,
            )

            st.session_state[
                "fx_macro_pair_snapshot"
            ] = snapshot.to_dict()

    snapshot = st.session_state.get(
        "fx_macro_pair_snapshot"
    )

    if not snapshot:
        st.info("Analyze a pair.")
        return

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Macro Score",
        snapshot.get("macro_score", 0),
    )

    c2.metric(
        "Confidence",
        snapshot.get("confidence_score", 0),
    )

    c3.metric(
        "Direction",
        snapshot.get("macro_direction"),
    )

    c4.metric(
        "Recommendation",
        snapshot.get(
            "macro_recommendation"
        ),
    )

    c5.metric(
        "CB Bias",
        snapshot.get(
            "central_bank_bias"
        ),
    )

    if snapshot.get("notes"):
        st.info(snapshot.get("notes"))

    st.divider()

    score_df = pd.DataFrame(
        [
            {
                "metric": "Macro Score",
                "score": snapshot.get(
                    "macro_score",
                    0,
                ),
            },
            {
                "metric": "Confidence",
                "score": snapshot.get(
                    "confidence_score",
                    0,
                ),
            },
            {
                "metric": "USD Strength",
                "score": snapshot.get(
                    "usd_strength_score",
                    0,
                ),
            },
            {
                "metric": "Risk On",
                "score": snapshot.get(
                    "risk_on_score",
                    0,
                ),
            },
            {
                "metric": "Risk Off",
                "score": snapshot.get(
                    "risk_off_score",
                    0,
                ),
            },
            {
                "metric": "Commodity",
                "score": snapshot.get(
                    "commodity_signal",
                    0,
                ),
            },
            {
                "metric": "Yield",
                "score": snapshot.get(
                    "yield_signal",
                    0,
                ),
            },
        ]
    )

    fig = px.bar(
        score_df,
        x="metric",
        y="score",
        title="Macro Factor Breakdown",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    st.json(snapshot)


# ============================================================
# Snapshots
# ============================================================

def render_snapshots(
    engine: ForexMacroEngine,
) -> None:

    st.subheader("Macro Snapshots")

    col1, col2, col3 = st.columns(3)

    pair = col1.text_input(
        "Pair Filter",
        value="",
        key="fx_macro_pair_filter",
    )

    direction = col2.selectbox(
        "Direction",
        [
            "ALL",
            "BULLISH",
            "BEARISH",
            "NEUTRAL",
        ],
        key="fx_macro_direction_filter",
    )

    recommendation = col3.selectbox(
        "Recommendation",
        [
            "ALL",
            "STRONG_BUY",
            "BUY",
            "WATCH",
            "SELL",
            "STRONG_SELL",
        ],
        key="fx_macro_recommendation_filter",
    )

    if st.button(
        "Load Snapshots",
        key="fx_macro_load_btn",
    ):
        rows = engine.load_snapshots(
            pair=pair or None,
            direction=direction,
            recommendation=recommendation,
            limit=5000,
        )

        st.session_state[
            "fx_macro_snapshots"
        ] = rows

    rows = st.session_state.get(
        "fx_macro_snapshots",
        [],
    )

    df = _df(rows)

    _grid(
        df,
        "fx_macro_snapshot_grid",
    )


# ============================================================
# Analytics
# ============================================================

def render_analytics(
    engine: ForexMacroEngine,
) -> None:

    st.subheader("Macro Analytics")

    rows = engine.load_snapshots(
        direction="ALL",
        recommendation="ALL",
        limit=5000,
    )

    df = _df(rows)

    if df.empty:
        st.info(
            "No macro snapshots available."
        )
        return

    c1, c2 = st.columns(2)

    with c1:
        _direction_chart(df)

    with c2:
        _recommendation_chart(df)

    c3, c4 = st.columns(2)

    with c3:
        _macro_score_chart(df)

    with c4:
        _confidence_chart(df)

    c5, c6 = st.columns(2)

    with c5:
        _rate_differential_chart(df)

    with c6:
        _growth_differential_chart(df)

    st.divider()

    _macro_scatter(df)

    st.divider()

    st.subheader(
        "Highest Conviction Macro Opportunities"
    )

    ranking_df = df.sort_values(
        by=[
            "macro_score",
            "confidence_score",
        ],
        ascending=False,
    )

    _grid(
        ranking_df.head(100),
        "fx_macro_rankings_grid",
    )


# ============================================================
# History
# ============================================================

def render_history(
    engine: ForexMacroEngine,
) -> None:

    st.subheader(
        "Macro Scan History"
    )

    if st.button(
        "Load History",
        key="fx_macro_history_btn",
    ):
        rows = engine.load_scans(
            limit=1000,
        )

        st.session_state[
            "fx_macro_history"
        ] = rows

    rows = st.session_state.get(
        "fx_macro_history",
        [],
    )

    df = _df(rows)

    if df.empty:
        st.info(
            "No macro history available."
        )
        return

    _grid(
        df,
        "fx_macro_history_grid",
    )

    if (
        "created_at" in df.columns
        and "avg_macro_score"
        in df.columns
    ):
        fig = px.line(
            df,
            x="created_at",
            y="avg_macro_score",
            title="Macro Score Trend",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    if (
        "created_at" in df.columns
        and "avg_confidence_score"
        in df.columns
    ):
        fig = px.line(
            df,
            x="created_at",
            y="avg_confidence_score",
            title="Macro Confidence Trend",
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
    macro_engine: Optional[
        ForexMacroEngine
    ] = None,
) -> None:
    render_forex_macro_dashboard(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
        macro_engine=macro_engine,
    )