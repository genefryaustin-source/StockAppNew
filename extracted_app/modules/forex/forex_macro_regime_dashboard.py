# modules/forex/forex_macro_regime_dashboard.py

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

    from modules.forex.forex_macro_regime_engine import (
        ForexMacroRegimeEngine,
        get_forex_macro_regime_engine,
    )

except Exception:

    from forex_service import (
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )

    from forex_macro_regime_engine import (
        ForexMacroRegimeEngine,
        get_forex_macro_regime_engine,
    )


DEFAULT_PAIRS = MAJOR_PAIRS + CROSS_PAIRS


# ==========================================================
# Helpers
# ==========================================================

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
            "No macro regime data available."
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


# ==========================================================
# Main Dashboard
# ==========================================================

def render_forex_macro_regime_dashboard(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    engine: Optional[
        ForexMacroRegimeEngine
    ] = None,
) -> None:

    engine = (
        engine
        or get_forex_macro_regime_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )
    )

    st.title(
        "Forex Macro Regime Dashboard"
    )

    st.caption(
        "Global Growth • Inflation • Monetary Policy • Risk Regime Intelligence"
    )

    workspace = st.radio(
        "Macro Regime Workspace",
        [
            "Regime Scanner",
            "Pair Analysis",
            "Regime Matrix",
            "Regime Rankings",
            "History",
        ],
        horizontal=True,
        key="forex_macro_regime_workspace",
    )

    if workspace == "Regime Scanner":
        render_scanner(engine)

    elif workspace == "Pair Analysis":
        render_pair_analysis(engine)

    elif workspace == "Regime Matrix":
        render_matrix(engine)

    elif workspace == "Regime Rankings":
        render_rankings(engine)

    elif workspace == "History":
        render_history(engine)


# ==========================================================
# Scanner
# ==========================================================

def render_scanner(
    engine: ForexMacroRegimeEngine,
) -> None:

    st.subheader(
        "Global Macro Regime Scanner"
    )

    col1, col2 = st.columns(2)

    universe = col1.selectbox(
        "Pair Universe",
        [
            "Major Pairs",
            "Cross Pairs",
            "All Pairs",
        ],
        key="macro_regime_universe",
    )

    save_scan = col2.checkbox(
        "Save Scan",
        value=True,
        key="macro_regime_save_scan",
    )

    if universe == "Major Pairs":
        pairs = MAJOR_PAIRS

    elif universe == "Cross Pairs":
        pairs = CROSS_PAIRS

    else:
        pairs = DEFAULT_PAIRS

    if st.button(
        "Run Macro Regime Scan",
        use_container_width=True,
        key="macro_regime_scan_btn",
    ):

        with st.spinner(
            "Analyzing macro environments..."
        ):

            scan = engine.scan_pairs(
                pairs=pairs,
                save=save_scan,
            )

            st.session_state[
                "forex_macro_regime_scan"
            ] = scan.to_dict()

    scan = st.session_state.get(
        "forex_macro_regime_scan"
    )

    if not scan:
        st.info(
            "Run a macro regime scan."
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
        "Expansion",
        scan.get(
            "expansion_count",
            0,
        ),
    )

    c3.metric(
        "Contraction",
        scan.get(
            "contraction_count",
            0,
        ),
    )

    c4.metric(
        "Inflationary",
        scan.get(
            "inflationary_count",
            0,
        ),
    )

    c5.metric(
        "Avg Score",
        scan.get(
            "average_regime_score",
            0,
        ),
    )

    df = _df(
        scan.get(
            "snapshots",
            [],
        )
    )

    display_cols = [
        c for c in [
            "pair",
            "macro_regime",
            "macro_regime_signal",
            "composite_macro_regime_score",
            "macro_conviction_score",
            "confidence_score",
        ]
        if c in df.columns
    ]

    _grid(
        df[display_cols]
        if not df.empty
        else df,
        "macro_regime_scan_grid",
    )


# ==========================================================
# Pair Analysis
# ==========================================================

def render_pair_analysis(
    engine: ForexMacroRegimeEngine,
) -> None:

    st.subheader(
        "Macro Regime Analysis"
    )

    pair = st.text_input(
        "Currency Pair",
        value="EUR/USD",
        key="macro_regime_pair",
    )

    if st.button(
        "Analyze Macro Regime",
        use_container_width=True,
        key="macro_regime_analyze_btn",
    ):

        snapshot = (
            engine.analyze_pair(
                pair,
                save=False,
            )
        )

        st.session_state[
            "macro_regime_snapshot"
        ] = snapshot.to_dict()

    snapshot = st.session_state.get(
        "macro_regime_snapshot"
    )

    if not snapshot:
        st.info(
            "Analyze a currency pair."
        )
        return

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Composite",
        snapshot.get(
            "composite_macro_regime_score",
            0,
        ),
    )

    c2.metric(
        "Growth",
        snapshot.get(
            "growth_regime_score",
            0,
        ),
    )

    c3.metric(
        "Inflation",
        snapshot.get(
            "inflation_regime_score",
            0,
        ),
    )

    c4.metric(
        "Risk",
        snapshot.get(
            "risk_regime_score",
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
                "Factor": "Macro",
                "Score": snapshot.get(
                    "macro_score",
                    0,
                ),
            },
            {
                "Factor": "Central Bank",
                "Score": snapshot.get(
                    "central_bank_score",
                    0,
                ),
            },
            {
                "Factor": "Sentiment",
                "Score": snapshot.get(
                    "sentiment_score",
                    0,
                ),
            },
            {
                "Factor": "Intermarket",
                "Score": snapshot.get(
                    "intermarket_score",
                    0,
                ),
            },
            {
                "Factor": "Risk",
                "Score": snapshot.get(
                    "risk_regime_score",
                    0,
                ),
            },
        ]
    )

    fig = px.bar(
        factor_df,
        x="Factor",
        y="Score",
        title=f"{pair} Macro Regime Components",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    st.json(snapshot)


# ==========================================================
# Matrix
# ==========================================================

def render_matrix(
    engine: ForexMacroRegimeEngine,
) -> None:

    st.subheader(
        "Macro Regime Matrix"
    )

    rows = engine.load_snapshots(
        limit=5000,
    )

    df = _df(rows)

    if df.empty:
        st.info(
            "No macro regime history available."
        )
        return

    if {
        "composite_macro_regime_score",
        "confidence_score",
    }.issubset(df.columns):

        fig = px.scatter(
            df,
            x="composite_macro_regime_score",
            y="confidence_score",
            color="macro_regime",
            size="macro_conviction_score",
            hover_name="pair",
            title="Macro Regime Matrix",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    _grid(
        df,
        "macro_regime_matrix_grid",
    )


# ==========================================================
# Rankings
# ==========================================================

def render_rankings(
    engine: ForexMacroRegimeEngine,
) -> None:

    st.subheader(
        "Macro Regime Rankings"
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
            "macro_conviction_score",
            ascending=False,
        )
        .head(25)
    )

    fig = px.bar(
        ranking_df,
        x="pair",
        y="macro_conviction_score",
        color="macro_regime",
        title="Highest Conviction Macro Regimes",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    fig2 = px.bar(
        ranking_df,
        x="pair",
        y="composite_macro_regime_score",
        color="macro_regime",
        title="Composite Macro Scores",
    )

    st.plotly_chart(
        fig2,
        use_container_width=True,
    )


# ==========================================================
# History
# ==========================================================

def render_history(
    engine: ForexMacroRegimeEngine,
) -> None:

    st.subheader(
        "Macro Regime History"
    )

    pair_filter = st.text_input(
        "Pair Filter",
        value="",
        key="macro_regime_history_filter",
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
        "macro_regime_history_grid",
    )

    if {
        "created_at",
        "composite_macro_regime_score",
    }.issubset(df.columns):

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=df["created_at"],
                y=df[
                    "composite_macro_regime_score"
                ],
                mode="lines+markers",
                name="Macro Score",
            )
        )

        fig.update_layout(
            title="Macro Regime Trend"
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )


# ==========================================================
# Public Entry Point
# ==========================================================

def render(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
) -> None:

    render_forex_macro_regime_dashboard(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )