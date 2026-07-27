# modules/forex/forex_relative_strength_dashboard.py

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

    from modules.forex.forex_relative_strength_engine import (
        ForexRelativeStrengthEngine,
        get_forex_relative_strength_engine,
    )

except Exception:

    from forex_service import (
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )

    from forex_relative_strength_engine import (
        ForexRelativeStrengthEngine,
        get_forex_relative_strength_engine,
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
        st.info("No relative strength data available.")
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

def render_forex_relative_strength_dashboard(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    engine: Optional[
        ForexRelativeStrengthEngine
    ] = None,
) -> None:

    engine = (
        engine
        or get_forex_relative_strength_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )
    )

    st.title(
        "Forex Relative Strength Dashboard"
    )

    st.caption(
        "Currency Strength • Relative Performance • Institutional Momentum"
    )

    workspace = st.radio(
        "Relative Strength Workspace",
        [
            "Scanner",
            "Pair Analysis",
            "Strength Matrix",
            "Currency Rankings",
            "History",
        ],
        horizontal=True,
        key="relative_strength_workspace",
    )

    if workspace == "Scanner":
        render_scanner(engine)

    elif workspace == "Pair Analysis":
        render_pair_analysis(engine)

    elif workspace == "Strength Matrix":
        render_strength_matrix(engine)

    elif workspace == "Currency Rankings":
        render_currency_rankings(engine)

    elif workspace == "History":
        render_history(engine)


# ============================================================
# Scanner
# ============================================================

def render_scanner(
    engine: ForexRelativeStrengthEngine,
) -> None:

    st.subheader(
        "Relative Strength Scanner"
    )

    col1, col2 = st.columns(2)

    pair_group = col1.selectbox(
        "Pair Universe",
        [
            "Major Pairs",
            "Cross Pairs",
            "All Pairs",
        ],
        key="relative_strength_pair_group",
    )

    save_scan = col2.checkbox(
        "Save Scan",
        value=True,
        key="relative_strength_save_scan",
    )

    if pair_group == "Major Pairs":
        pairs = MAJOR_PAIRS

    elif pair_group == "Cross Pairs":
        pairs = CROSS_PAIRS

    else:
        pairs = DEFAULT_PAIRS

    if st.button(
        "Run Relative Strength Scan",
        use_container_width=True,
        key="relative_strength_scan_button",
    ):

        with st.spinner(
            "Analyzing currency strength..."
        ):

            scan = engine.scan_pairs(
                pairs=pairs,
                save=save_scan,
            )

            st.session_state[
                "relative_strength_scan"
            ] = scan.to_dict()

    scan = st.session_state.get(
        "relative_strength_scan"
    )

    if not scan:
        st.info(
            "Run a relative strength scan."
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
        "Bullish",
        scan.get(
            "bullish_count",
            0,
        ),
    )

    c3.metric(
        "Bearish",
        scan.get(
            "bearish_count",
            0,
        ),
    )

    c4.metric(
        "Avg Strength",
        scan.get(
            "average_strength_score",
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
            "base_currency",
            "quote_currency",
            "relative_strength_score",
            "currency_spread_score",
            "momentum_score",
            "conviction_score",
            "strength_direction",
            "strength_signal",
            "confidence_score",
        ]
        if c in df.columns
    ]

    _grid(
        df[display_cols]
        if not df.empty
        else df,
        "relative_strength_scan_grid",
    )


# ============================================================
# Pair Analysis
# ============================================================

def render_pair_analysis(
    engine: ForexRelativeStrengthEngine,
) -> None:

    st.subheader(
        "Relative Strength Analysis"
    )

    pair = st.text_input(
        "Currency Pair",
        value="EUR/USD",
        key="relative_strength_pair",
    )

    if st.button(
        "Analyze Relative Strength",
        use_container_width=True,
        key="relative_strength_pair_button",
    ):

        snapshot = engine.analyze_pair(
            pair,
            save=False,
        )

        st.session_state[
            "relative_strength_snapshot"
        ] = snapshot.to_dict()

    snapshot = st.session_state.get(
        "relative_strength_snapshot"
    )

    if not snapshot:
        st.info(
            "Analyze a currency pair."
        )
        return

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Base Strength",
        snapshot.get(
            "base_strength_score",
            0,
        ),
    )

    c2.metric(
        "Quote Strength",
        snapshot.get(
            "quote_strength_score",
            0,
        ),
    )

    c3.metric(
        "Relative",
        snapshot.get(
            "relative_strength_score",
            0,
        ),
    )

    c4.metric(
        "Momentum",
        snapshot.get(
            "momentum_score",
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
                "Factor": "Base",
                "Score": snapshot.get(
                    "base_strength_score",
                    0,
                ),
            },
            {
                "Factor": "Quote",
                "Score": snapshot.get(
                    "quote_strength_score",
                    0,
                ),
            },
            {
                "Factor": "Macro",
                "Score": snapshot.get(
                    "macro_strength_score",
                    0,
                ),
            },
            {
                "Factor": "Flow",
                "Score": snapshot.get(
                    "flow_strength_score",
                    0,
                ),
            },
            {
                "Factor": "Structure",
                "Score": snapshot.get(
                    "structure_strength_score",
                    0,
                ),
            },
            {
                "Factor": "Conviction",
                "Score": snapshot.get(
                    "conviction_score",
                    0,
                ),
            },
        ]
    )

    fig = px.bar(
        factor_df,
        x="Factor",
        y="Score",
        title=f"{pair} Relative Strength Factors",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    st.json(snapshot)


# ============================================================
# Strength Matrix
# ============================================================

def render_strength_matrix(
    engine: ForexRelativeStrengthEngine,
) -> None:

    st.subheader(
        "Relative Strength Matrix"
    )

    rows = engine.load_snapshots(
        limit=5000,
    )

    df = _df(rows)

    if df.empty:
        st.info(
            "No relative strength history available."
        )
        return

    if {
        "relative_strength_score",
        "confidence_score",
    }.issubset(df.columns):

        fig = px.scatter(
            df,
            x="relative_strength_score",
            y="confidence_score",
            color="strength_direction",
            size="conviction_score",
            hover_name="pair",
            title="Relative Strength Matrix",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    _grid(
        df,
        "relative_strength_matrix_grid",
    )


# ============================================================
# Rankings
# ============================================================

def render_currency_rankings(
    engine: ForexRelativeStrengthEngine,
) -> None:

    st.subheader(
        "Currency Strength Rankings"
    )

    rows = engine.load_snapshots(
        limit=5000,
    )

    df = _df(rows)

    if df.empty:
        st.info(
            "No rankings available."
        )
        return

    if {
        "pair",
        "conviction_score",
    }.issubset(df.columns):

        fig = px.bar(
            df.sort_values(
                "conviction_score",
                ascending=False,
            ).head(20),
            x="pair",
            y="conviction_score",
            color="strength_direction",
            title="Conviction Ranking",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    if {
        "pair",
        "relative_strength_score",
    }.issubset(df.columns):

        fig2 = px.bar(
            df.sort_values(
                "relative_strength_score",
                ascending=False,
            ).head(20),
            x="pair",
            y="relative_strength_score",
            color="strength_direction",
            title="Relative Strength Ranking",
        )

        st.plotly_chart(
            fig2,
            use_container_width=True,
        )


# ============================================================
# History
# ============================================================

def render_history(
    engine: ForexRelativeStrengthEngine,
) -> None:

    st.subheader(
        "Relative Strength History"
    )

    pair = st.text_input(
        "History Pair Filter",
        value="",
        key="relative_strength_history_pair",
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
        "relative_strength_history_grid",
    )

    if {
        "created_at",
        "relative_strength_score",
    }.issubset(df.columns):

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=df["created_at"],
                y=df[
                    "relative_strength_score"
                ],
                mode="lines+markers",
                name="Relative Strength",
            )
        )

        fig.update_layout(
            title="Relative Strength Trend"
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

    render_forex_relative_strength_dashboard(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )