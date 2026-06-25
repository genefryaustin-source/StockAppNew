# modules/forex/forex_market_structure_dashboard.py

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

    from modules.forex.forex_market_structure_engine import (
        ForexMarketStructureEngine,
        get_forex_market_structure_engine,
    )

except Exception:

    from forex_service import (
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )

    from forex_market_structure_engine import (
        ForexMarketStructureEngine,
        get_forex_market_structure_engine,
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
        st.info("No market structure data available.")
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

def render_forex_market_structure_dashboard(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    engine: Optional[
        ForexMarketStructureEngine
    ] = None,
) -> None:

    engine = (
        engine
        or get_forex_market_structure_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )
    )

    st.title(
        "Forex Market Structure Dashboard"
    )

    st.caption(
        "Trend Structure • Breakout Risk • Reversal Risk • Support & Resistance Intelligence"
    )

    workspace = st.radio(
        "Market Structure Workspace",
        [
            "Scanner",
            "Pair Analysis",
            "Structure Matrix",
            "Regime Monitor",
            "History",
        ],
        horizontal=True,
        key="market_structure_workspace",
    )

    if workspace == "Scanner":
        render_scanner(engine)

    elif workspace == "Pair Analysis":
        render_pair_analysis(engine)

    elif workspace == "Structure Matrix":
        render_structure_matrix(engine)

    elif workspace == "Regime Monitor":
        render_regime_monitor(engine)

    elif workspace == "History":
        render_history(engine)


# ============================================================
# Scanner
# ============================================================

def render_scanner(
    engine: ForexMarketStructureEngine,
) -> None:

    st.subheader(
        "Institutional Market Structure Scanner"
    )

    col1, col2 = st.columns(2)

    pair_group = col1.selectbox(
        "Pair Universe",
        [
            "Major Pairs",
            "Cross Pairs",
            "All Pairs",
        ],
        key="market_structure_pair_group",
    )

    save_scan = col2.checkbox(
        "Save Scan",
        value=True,
        key="market_structure_save_scan",
    )

    if pair_group == "Major Pairs":
        pairs = MAJOR_PAIRS

    elif pair_group == "Cross Pairs":
        pairs = CROSS_PAIRS

    else:
        pairs = DEFAULT_PAIRS

    if st.button(
        "Run Market Structure Scan",
        use_container_width=True,
        key="market_structure_scan_button",
    ):

        with st.spinner(
            "Analyzing market structure..."
        ):

            scan = engine.scan_pairs(
                pairs=pairs,
                save=save_scan,
            )

            st.session_state[
                "market_structure_scan"
            ] = scan.to_dict()

    scan = st.session_state.get(
        "market_structure_scan"
    )

    if not scan:
        st.info(
            "Run a market structure scan."
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
        "Bull Trends",
        scan.get(
            "bullish_count",
            0,
        ),
    )

    c3.metric(
        "Bear Trends",
        scan.get(
            "bearish_count",
            0,
        ),
    )

    c4.metric(
        "Ranges",
        scan.get(
            "range_count",
            0,
        ),
    )

    c5.metric(
        "Avg Score",
        scan.get(
            "average_structure_score",
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
            "market_structure_score",
            "structure_strength",
            "structure_regime",
            "structure_signal",
            "breakout_probability",
            "reversal_probability",
            "support_strength",
            "resistance_strength",
            "confidence_score",
        ]
        if c in df.columns
    ]

    _grid(
        df[display_cols]
        if not df.empty
        else df,
        "market_structure_scan_grid",
    )


# ============================================================
# Pair Analysis
# ============================================================

def render_pair_analysis(
    engine: ForexMarketStructureEngine,
) -> None:

    st.subheader(
        "Market Structure Analysis"
    )

    pair = st.text_input(
        "Currency Pair",
        value="EUR/USD",
        key="market_structure_pair",
    )

    if st.button(
        "Analyze Structure",
        use_container_width=True,
        key="market_structure_pair_button",
    ):

        snapshot = engine.analyze_pair(
            pair,
            save=False,
        )

        st.session_state[
            "market_structure_snapshot"
        ] = snapshot.to_dict()

    snapshot = st.session_state.get(
        "market_structure_snapshot"
    )

    if not snapshot:
        st.info(
            "Analyze a currency pair."
        )
        return

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Structure",
        snapshot.get(
            "market_structure_score",
            0,
        ),
    )

    c2.metric(
        "Breakout %",
        snapshot.get(
            "breakout_probability",
            0,
        ),
    )

    c3.metric(
        "Reversal %",
        snapshot.get(
            "reversal_probability",
            0,
        ),
    )

    c4.metric(
        "Support",
        snapshot.get(
            "support_strength",
            0,
        ),
    )

    c5.metric(
        "Resistance",
        snapshot.get(
            "resistance_strength",
            0,
        ),
    )

    factor_df = pd.DataFrame(
        [
            {
                "Factor": "Trend",
                "Value": snapshot.get(
                    "trend_score",
                    0,
                ),
            },
            {
                "Factor": "Liquidity",
                "Value": snapshot.get(
                    "liquidity_score",
                    0,
                ),
            },
            {
                "Factor": "Positioning",
                "Value": snapshot.get(
                    "positioning_score",
                    0,
                ),
            },
            {
                "Factor": "Breakout",
                "Value": snapshot.get(
                    "breakout_probability",
                    0,
                ),
            },
            {
                "Factor": "Reversal",
                "Value": snapshot.get(
                    "reversal_probability",
                    0,
                ),
            },
            {
                "Factor": "Confidence",
                "Value": snapshot.get(
                    "confidence_score",
                    0,
                ),
            },
        ]
    )

    fig = px.bar(
        factor_df,
        x="Factor",
        y="Value",
        title=f"{pair} Market Structure Factors",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    st.json(snapshot)


# ============================================================
# Structure Matrix
# ============================================================

def render_structure_matrix(
    engine: ForexMarketStructureEngine,
) -> None:

    st.subheader(
        "Market Structure Matrix"
    )

    rows = engine.load_snapshots(
        limit=5000,
    )

    df = _df(rows)

    if df.empty:
        st.info(
            "No market structure history available."
        )
        return

    if {
        "market_structure_score",
        "confidence_score",
    }.issubset(df.columns):

        fig = px.scatter(
            df,
            x="market_structure_score",
            y="confidence_score",
            color="structure_regime",
            size="structure_strength",
            hover_name="pair",
            title="Structure Matrix",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    _grid(
        df,
        "market_structure_matrix_grid",
    )


# ============================================================
# Regime Monitor
# ============================================================

def render_regime_monitor(
    engine: ForexMarketStructureEngine,
) -> None:

    st.subheader(
        "Market Regime Monitor"
    )

    rows = engine.load_snapshots(
        limit=5000,
    )

    df = _df(rows)

    if df.empty:
        st.info(
            "No market structure data."
        )
        return

    if "structure_regime" not in df.columns:
        return

    regime_df = (
        df.groupby(
            "structure_regime"
        )
        .size()
        .reset_index(
            name="count"
        )
    )

    fig = px.pie(
        regime_df,
        names="structure_regime",
        values="count",
        title="Market Regime Distribution",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    if {
        "pair",
        "market_structure_score",
    }.issubset(df.columns):

        fig2 = px.bar(
            df.sort_values(
                "market_structure_score",
                ascending=False,
            ).head(20),
            x="pair",
            y="market_structure_score",
            color="structure_regime",
            title="Top Structure Scores",
        )

        st.plotly_chart(
            fig2,
            use_container_width=True,
        )

    if {
        "pair",
        "breakout_probability",
    }.issubset(df.columns):

        fig3 = px.bar(
            df.sort_values(
                "breakout_probability",
                ascending=False,
            ).head(20),
            x="pair",
            y="breakout_probability",
            color="structure_signal",
            title="Breakout Risk Ranking",
        )

        st.plotly_chart(
            fig3,
            use_container_width=True,
        )


# ============================================================
# History
# ============================================================

def render_history(
    engine: ForexMarketStructureEngine,
) -> None:

    st.subheader(
        "Market Structure History"
    )

    pair = st.text_input(
        "History Pair Filter",
        value="",
        key="market_structure_history_pair",
    )

    rows = engine.load_snapshots(
        pair=pair if pair else None,
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
        "market_structure_history_grid",
    )

    if {
        "created_at",
        "market_structure_score",
    }.issubset(df.columns):

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=df["created_at"],
                y=df[
                    "market_structure_score"
                ],
                mode="lines+markers",
                name="Structure Score",
            )
        )

        fig.update_layout(
            title="Market Structure Trend"
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

    render_forex_market_structure_dashboard(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )