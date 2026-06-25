# modules/forex/forex_flow_of_funds_dashboard.py

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

    from modules.forex.forex_flow_of_funds_engine import (
        ForexFlowOfFundsEngine,
        get_forex_flow_of_funds_engine,
    )

except Exception:

    from forex_service import (
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )

    from forex_flow_of_funds_engine import (
        ForexFlowOfFundsEngine,
        get_forex_flow_of_funds_engine,
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
        st.info("No flow-of-funds data available.")
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

def render_forex_flow_of_funds_dashboard(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    engine: Optional[
        ForexFlowOfFundsEngine
    ] = None,
) -> None:

    engine = (
        engine
        or get_forex_flow_of_funds_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )
    )

    st.title(
        "Forex Flow Of Funds Dashboard"
    )

    st.caption(
        "Institutional Capital Flows • Dealer Capital Rotation • Macro Fund Flows"
    )

    workspace = st.radio(
        "Flow Of Funds Workspace",
        [
            "Scanner",
            "Pair Analysis",
            "Capital Rotation",
            "Fund Flow Matrix",
            "History",
        ],
        horizontal=True,
        key="flow_of_funds_workspace",
    )

    if workspace == "Scanner":
        render_scanner(engine)

    elif workspace == "Pair Analysis":
        render_pair_analysis(engine)

    elif workspace == "Capital Rotation":
        render_capital_rotation(engine)

    elif workspace == "Fund Flow Matrix":
        render_matrix(engine)

    elif workspace == "History":
        render_history(engine)


# ============================================================
# Scanner
# ============================================================

def render_scanner(
    engine: ForexFlowOfFundsEngine,
) -> None:

    st.subheader(
        "Institutional Flow Of Funds Scanner"
    )

    col1, col2 = st.columns(2)

    pair_group = col1.selectbox(
        "Pair Universe",
        [
            "Major Pairs",
            "Cross Pairs",
            "All Pairs",
        ],
        key="flow_funds_pair_group",
    )

    save_scan = col2.checkbox(
        "Save Scan",
        value=True,
        key="flow_funds_save_scan",
    )

    if pair_group == "Major Pairs":
        pairs = MAJOR_PAIRS

    elif pair_group == "Cross Pairs":
        pairs = CROSS_PAIRS

    else:
        pairs = DEFAULT_PAIRS

    if st.button(
        "Run Flow Of Funds Scan",
        use_container_width=True,
        key="flow_funds_scan_button",
    ):

        with st.spinner(
            "Analyzing institutional capital flows..."
        ):

            scan = engine.scan_pairs(
                pairs=pairs,
                save=save_scan,
            )

            st.session_state[
                "flow_of_funds_scan"
            ] = scan.to_dict()

    scan = st.session_state.get(
        "flow_of_funds_scan"
    )

    if not scan:
        st.info(
            "Run a flow-of-funds scan."
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
        "Inflows",
        scan.get(
            "inflow_count",
            0,
        ),
    )

    c3.metric(
        "Outflows",
        scan.get(
            "outflow_count",
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
        "Avg Net Flow",
        scan.get(
            "average_net_flow",
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
            "flow_direction",
            "flow_signal",
            "net_flow_score",
            "institutional_inflow_score",
            "institutional_outflow_score",
            "capital_rotation_score",
            "capital_momentum_score",
            "confidence_score",
        ]
        if c in df.columns
    ]

    _grid(
        df[display_cols]
        if not df.empty
        else df,
        "flow_of_funds_scan_grid",
    )


# ============================================================
# Pair Analysis
# ============================================================

def render_pair_analysis(
    engine: ForexFlowOfFundsEngine,
) -> None:

    st.subheader(
        "Flow Of Funds Pair Analysis"
    )

    pair = st.text_input(
        "Currency Pair",
        value="EUR/USD",
        key="flow_of_funds_pair",
    )

    if st.button(
        "Analyze Pair",
        use_container_width=True,
        key="flow_of_funds_pair_button",
    ):

        snapshot = engine.analyze_pair(
            pair,
            save=False,
        )

        st.session_state[
            "flow_of_funds_snapshot"
        ] = snapshot.to_dict()

    snapshot = st.session_state.get(
        "flow_of_funds_snapshot"
    )

    if not snapshot:
        st.info(
            "Analyze a currency pair."
        )
        return

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Net Flow",
        snapshot.get(
            "net_flow_score",
            0,
        ),
    )

    c2.metric(
        "Inflow",
        snapshot.get(
            "institutional_inflow_score",
            0,
        ),
    )

    c3.metric(
        "Outflow",
        snapshot.get(
            "institutional_outflow_score",
            0,
        ),
    )

    c4.metric(
        "Rotation",
        snapshot.get(
            "capital_rotation_score",
            0,
        ),
    )

    c5.metric(
        "Momentum",
        snapshot.get(
            "capital_momentum_score",
            0,
        ),
    )

    factor_df = pd.DataFrame(
        [
            {
                "Factor": "Dealer",
                "Score": snapshot.get(
                    "dealer_flow_score",
                    0,
                ),
            },
            {
                "Factor": "Macro",
                "Score": snapshot.get(
                    "macro_flow_score",
                    0,
                ),
            },
            {
                "Factor": "Liquidity",
                "Score": snapshot.get(
                    "liquidity_flow_score",
                    0,
                ),
            },
            {
                "Factor": "Speculative",
                "Score": snapshot.get(
                    "speculative_flow_score",
                    0,
                ),
            },
            {
                "Factor": "Rotation",
                "Score": snapshot.get(
                    "capital_rotation_score",
                    0,
                ),
            },
            {
                "Factor": "Momentum",
                "Score": snapshot.get(
                    "capital_momentum_score",
                    0,
                ),
            },
        ]
    )

    fig = px.bar(
        factor_df,
        x="Factor",
        y="Score",
        title=f"{pair} Flow Of Funds Factors",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    st.json(snapshot)


# ============================================================
# Capital Rotation
# ============================================================

def render_capital_rotation(
    engine: ForexFlowOfFundsEngine,
) -> None:

    st.subheader(
        "Institutional Capital Rotation"
    )

    rows = engine.load_snapshots(
        limit=5000,
    )

    df = _df(rows)

    if df.empty:
        st.info(
            "No capital flow history available."
        )
        return

    if {
        "pair",
        "capital_rotation_score",
    }.issubset(df.columns):

        fig = px.bar(
            df.sort_values(
                "capital_rotation_score",
                ascending=False,
            ).head(20),
            x="pair",
            y="capital_rotation_score",
            color="flow_direction",
            title="Capital Rotation Ranking",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    if {
        "pair",
        "capital_momentum_score",
    }.issubset(df.columns):

        fig2 = px.bar(
            df.sort_values(
                "capital_momentum_score",
                ascending=False,
            ).head(20),
            x="pair",
            y="capital_momentum_score",
            color="flow_direction",
            title="Capital Momentum Ranking",
        )

        st.plotly_chart(
            fig2,
            use_container_width=True,
        )


# ============================================================
# Flow Matrix
# ============================================================

def render_matrix(
    engine: ForexFlowOfFundsEngine,
) -> None:

    st.subheader(
        "Institutional Flow Matrix"
    )

    rows = engine.load_snapshots(
        limit=5000,
    )

    df = _df(rows)

    if df.empty:
        st.info(
            "No fund flow history available."
        )
        return

    if {
        "net_flow_score",
        "confidence_score",
    }.issubset(df.columns):

        fig = px.scatter(
            df,
            x="net_flow_score",
            y="confidence_score",
            color="flow_direction",
            size="capital_rotation_score",
            hover_name="pair",
            title="Flow Matrix",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    _grid(
        df,
        "flow_of_funds_matrix_grid",
    )


# ============================================================
# History
# ============================================================

def render_history(
    engine: ForexFlowOfFundsEngine,
) -> None:

    st.subheader(
        "Flow Of Funds History"
    )

    pair = st.text_input(
        "History Pair Filter",
        value="",
        key="flow_of_funds_history_pair",
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
        "flow_of_funds_history_grid",
    )

    if {
        "created_at",
        "net_flow_score",
    }.issubset(df.columns):

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=df["created_at"],
                y=df[
                    "net_flow_score"
                ],
                mode="lines+markers",
                name="Net Flow",
            )
        )

        fig.update_layout(
            title="Institutional Net Flow Trend"
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

    render_forex_flow_of_funds_dashboard(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )