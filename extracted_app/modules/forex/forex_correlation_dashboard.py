# modules/forex/forex_correlation_dashboard.py

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

    from modules.forex.forex_correlation_engine import (
        ForexCorrelationEngine,
        get_forex_correlation_engine,
    )

except Exception:

    from forex_service import (
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )

    from forex_correlation_engine import (
        ForexCorrelationEngine,
        get_forex_correlation_engine,
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
        st.info("No correlation data available.")
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

def render_forex_correlation_dashboard(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    engine: Optional[
        ForexCorrelationEngine
    ] = None,
) -> None:

    engine = (
        engine
        or get_forex_correlation_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )
    )

    st.title(
        "Forex Correlation Dashboard"
    )

    st.caption(
        "Intermarket Correlation • Pair Alignment • Divergence Intelligence"
    )

    workspace = st.radio(
        "Correlation Workspace",
        [
            "Correlation Scanner",
            "Pair Correlation",
            "Correlation Matrix",
            "Correlation Rankings",
            "History",
        ],
        horizontal=True,
        key="forex_correlation_workspace",
    )

    if workspace == "Correlation Scanner":
        render_scanner(engine)

    elif workspace == "Pair Correlation":
        render_pair_analysis(engine)

    elif workspace == "Correlation Matrix":
        render_matrix(engine)

    elif workspace == "Correlation Rankings":
        render_rankings(engine)

    elif workspace == "History":
        render_history(engine)


# ============================================================
# Scanner
# ============================================================

def render_scanner(
    engine: ForexCorrelationEngine,
) -> None:

    st.subheader(
        "Institutional Correlation Scanner"
    )

    universe = st.selectbox(
        "Pair Universe",
        [
            "Major Pairs",
            "Cross Pairs",
            "All Pairs",
        ],
        key="correlation_universe",
    )

    save_scan = st.checkbox(
        "Save Scan",
        value=True,
        key="correlation_save_scan",
    )

    if universe == "Major Pairs":
        pairs = MAJOR_PAIRS

    elif universe == "Cross Pairs":
        pairs = CROSS_PAIRS

    else:
        pairs = DEFAULT_PAIRS

    if st.button(
        "Run Correlation Scan",
        use_container_width=True,
        key="run_correlation_scan",
    ):

        with st.spinner(
            "Building institutional correlation matrix..."
        ):

            scan = engine.scan_correlations(
                pairs=pairs,
                save=save_scan,
            )

            st.session_state[
                "forex_correlation_scan"
            ] = scan.to_dict()

    scan = st.session_state.get(
        "forex_correlation_scan"
    )

    if not scan:
        st.info(
            "Run a correlation scan."
        )
        return

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Pairs",
        scan.get(
            "pair_count",
            0,
        ),
    )

    c2.metric(
        "Positive",
        scan.get(
            "positive_count",
            0,
        ),
    )

    c3.metric(
        "Negative",
        scan.get(
            "negative_count",
            0,
        ),
    )

    c4.metric(
        "Neutral",
        scan.get(
            "neutral_count",
            0,
        ),
    )

    c5.metric(
        "Avg Correlation",
        scan.get(
            "average_correlation",
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
            "pair_a",
            "pair_b",
            "correlation_score",
            "inverse_correlation_score",
            "correlation_regime",
            "correlation_signal",
            "confidence_score",
        ]
        if c in df.columns
    ]

    _grid(
        df[cols]
        if not df.empty
        else df,
        "correlation_scan_grid",
    )


# ============================================================
# Pair Analysis
# ============================================================

def render_pair_analysis(
    engine: ForexCorrelationEngine,
) -> None:

    st.subheader(
        "Pair Correlation Analysis"
    )

    col1, col2 = st.columns(2)

    pair_a = col1.text_input(
        "Pair A",
        value="EUR/USD",
        key="corr_pair_a",
    )

    pair_b = col2.text_input(
        "Pair B",
        value="GBP/USD",
        key="corr_pair_b",
    )

    if st.button(
        "Analyze Correlation",
        use_container_width=True,
        key="analyze_pair_corr",
    ):

        snapshot = (
            engine.analyze_pair_correlation(
                pair_a,
                pair_b,
                save=False,
            )
        )

        st.session_state[
            "pair_corr_snapshot"
        ] = snapshot.to_dict()

    snapshot = st.session_state.get(
        "pair_corr_snapshot"
    )

    if not snapshot:
        st.info(
            "Analyze a pair relationship."
        )
        return

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Correlation",
        snapshot.get(
            "correlation_score",
            0,
        ),
    )

    c2.metric(
        "Inverse",
        snapshot.get(
            "inverse_correlation_score",
            0,
        ),
    )

    c3.metric(
        "Strength",
        snapshot.get(
            "strength_score",
            0,
        ),
    )

    c4.metric(
        "Stability",
        snapshot.get(
            "stability_score",
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
                "Factor": "Relative Strength",
                "Value": snapshot.get(
                    "relative_strength_alignment",
                    0,
                ),
            },
            {
                "Factor": "Flow Alignment",
                "Value": snapshot.get(
                    "capital_flow_alignment",
                    0,
                ),
            },
            {
                "Factor": "Structure Alignment",
                "Value": snapshot.get(
                    "structure_alignment",
                    0,
                ),
            },
            {
                "Factor": "Correlation",
                "Value": snapshot.get(
                    "correlation_score",
                    0,
                ),
            },
        ]
    )

    fig = px.bar(
        chart_df,
        x="Factor",
        y="Value",
        title="Correlation Components",
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
    engine: ForexCorrelationEngine,
) -> None:

    st.subheader(
        "Correlation Matrix"
    )

    rows = engine.load_snapshots(
        limit=5000,
    )

    df = _df(rows)

    if df.empty:
        st.info(
            "No correlation history available."
        )
        return

    if {
        "correlation_score",
        "confidence_score",
    }.issubset(df.columns):

        fig = px.scatter(
            df,
            x="correlation_score",
            y="confidence_score",
            color="correlation_regime",
            size="strength_score",
            hover_data=[
                "pair_a",
                "pair_b",
            ],
            title="Institutional Correlation Matrix",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    _grid(
        df,
        "correlation_matrix_grid",
    )


# ============================================================
# Rankings
# ============================================================

def render_rankings(
    engine: ForexCorrelationEngine,
) -> None:

    st.subheader(
        "Correlation Rankings"
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

    top_corr = (
        df.sort_values(
            "correlation_score",
            ascending=False,
        )
        .head(20)
    )

    fig = px.bar(
        top_corr,
        x="pair_a",
        y="correlation_score",
        color="pair_b",
        title="Top Positive Correlations",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    top_inverse = (
        df.sort_values(
            "correlation_score",
            ascending=True,
        )
        .head(20)
    )

    fig2 = px.bar(
        top_inverse,
        x="pair_a",
        y="correlation_score",
        color="pair_b",
        title="Top Negative Correlations",
    )

    st.plotly_chart(
        fig2,
        use_container_width=True,
    )


# ============================================================
# History
# ============================================================

def render_history(
    engine: ForexCorrelationEngine,
) -> None:

    st.subheader(
        "Correlation History"
    )

    rows = engine.load_snapshots(
        limit=5000,
    )

    df = _df(rows)

    if df.empty:
        st.info(
            "No historical correlations available."
        )
        return

    _grid(
        df,
        "correlation_history_grid",
    )

    if {
        "created_at",
        "correlation_score",
    }.issubset(df.columns):

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=df["created_at"],
                y=df[
                    "correlation_score"
                ],
                mode="lines+markers",
                name="Correlation",
            )
        )

        fig.update_layout(
            title="Correlation Trend"
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

    render_forex_correlation_dashboard(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )