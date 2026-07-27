# modules/forex/forex_central_bank_dashboard.py

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

    from modules.forex.forex_central_bank_engine import (
        ForexCentralBankEngine,
        get_forex_central_bank_engine,
        CENTRAL_BANKS,
    )

except Exception:

    from forex_service import (
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )

    from forex_central_bank_engine import (
        ForexCentralBankEngine,
        get_forex_central_bank_engine,
        CENTRAL_BANKS,
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
            "No central bank data available."
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

def render_forex_central_bank_dashboard(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    engine: Optional[
        ForexCentralBankEngine
    ] = None,
) -> None:

    engine = (
        engine
        or get_forex_central_bank_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )
    )

    st.title(
        "Forex Central Bank Dashboard"
    )

    st.caption(
        "Federal Reserve • ECB • BOE • BOJ • SNB • RBA • BOC • RBNZ Intelligence"
    )

    workspace = st.radio(
        "Central Bank Workspace",
        [
            "Policy Scanner",
            "Pair Analysis",
            "Policy Matrix",
            "Central Banks",
            "History",
        ],
        horizontal=True,
        key="central_bank_workspace",
    )

    if workspace == "Policy Scanner":
        render_scanner(engine)

    elif workspace == "Pair Analysis":
        render_pair_analysis(engine)

    elif workspace == "Policy Matrix":
        render_matrix(engine)

    elif workspace == "Central Banks":
        render_central_banks()

    elif workspace == "History":
        render_history(engine)


# ==========================================================
# Scanner
# ==========================================================

def render_scanner(
    engine: ForexCentralBankEngine,
) -> None:

    st.subheader(
        "Global Monetary Policy Scanner"
    )

    col1, col2 = st.columns(2)

    universe = col1.selectbox(
        "Pair Universe",
        [
            "Major Pairs",
            "Cross Pairs",
            "All Pairs",
        ],
        key="cb_universe",
    )

    save_scan = col2.checkbox(
        "Save Scan",
        value=True,
        key="cb_save_scan",
    )

    if universe == "Major Pairs":
        pairs = MAJOR_PAIRS

    elif universe == "Cross Pairs":
        pairs = CROSS_PAIRS

    else:
        pairs = DEFAULT_PAIRS

    if st.button(
        "Run Central Bank Scan",
        use_container_width=True,
        key="cb_scan_button",
    ):

        with st.spinner(
            "Analyzing global central bank policy..."
        ):

            scan = engine.scan_pairs(
                pairs=pairs,
                save=save_scan,
            )

            st.session_state[
                "central_bank_scan"
            ] = scan.to_dict()

    scan = st.session_state.get(
        "central_bank_scan"
    )

    if not scan:
        st.info(
            "Run a policy scan."
        )
        return

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Pairs",
        scan.get(
            "pair_count",
            0,
        ),
    )

    c2.metric(
        "Bullish Policy",
        scan.get(
            "bullish_policy_count",
            0,
        ),
    )

    c3.metric(
        "Bearish Policy",
        scan.get(
            "bearish_policy_count",
            0,
        ),
    )

    c4.metric(
        "Average Score",
        scan.get(
            "average_score",
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
            "pair",
            "policy_regime",
            "policy_signal",
            "central_bank_score",
            "policy_divergence_score",
            "rate_differential_score",
            "confidence_score",
        ]
        if c in df.columns
    ]

    _grid(
        df[cols]
        if not df.empty
        else df,
        "cb_scan_grid",
    )


# ==========================================================
# Pair Analysis
# ==========================================================

def render_pair_analysis(
    engine: ForexCentralBankEngine,
) -> None:

    st.subheader(
        "Central Bank Pair Analysis"
    )

    pair = st.text_input(
        "Currency Pair",
        value="EUR/USD",
        key="cb_pair_analysis",
    )

    if st.button(
        "Analyze Policy Divergence",
        use_container_width=True,
        key="cb_analyze_btn",
    ):

        snapshot = (
            engine.analyze_pair(
                pair,
                save=False,
            )
        )

        st.session_state[
            "cb_snapshot"
        ] = snapshot.to_dict()

    snapshot = st.session_state.get(
        "cb_snapshot"
    )

    if not snapshot:
        st.info(
            "Analyze a currency pair."
        )
        return

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "CB Score",
        snapshot.get(
            "central_bank_score",
            0,
        ),
    )

    c2.metric(
        "Policy Divergence",
        snapshot.get(
            "policy_divergence_score",
            0,
        ),
    )

    c3.metric(
        "Rate Differential",
        snapshot.get(
            "rate_differential_score",
            0,
        ),
    )

    c4.metric(
        "Macro",
        snapshot.get(
            "macro_score",
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
                "Factor": "Policy",
                "Score": snapshot.get(
                    "policy_divergence_score",
                    0,
                ),
            },
            {
                "Factor": "Rates",
                "Score": snapshot.get(
                    "rate_differential_score",
                    0,
                ),
            },
            {
                "Factor": "Strength",
                "Score": snapshot.get(
                    "currency_strength_score",
                    0,
                ),
            },
            {
                "Factor": "Macro",
                "Score": snapshot.get(
                    "macro_score",
                    0,
                ),
            },
            {
                "Factor": "Composite",
                "Score": snapshot.get(
                    "central_bank_score",
                    0,
                ),
            },
        ]
    )

    fig = px.bar(
        chart_df,
        x="Factor",
        y="Score",
        title=f"{pair} Central Bank Factors",
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
    engine: ForexCentralBankEngine,
) -> None:

    st.subheader(
        "Policy Divergence Matrix"
    )

    rows = engine.load_snapshots(
        limit=5000,
    )

    df = _df(rows)

    if df.empty:
        st.info(
            "No policy history available."
        )
        return

    if {
        "central_bank_score",
        "confidence_score",
    }.issubset(df.columns):

        fig = px.scatter(
            df,
            x="central_bank_score",
            y="confidence_score",
            color="policy_regime",
            size="policy_divergence_score",
            hover_name="pair",
            title="Central Bank Divergence Matrix",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    _grid(
        df,
        "cb_matrix_grid",
    )


# ==========================================================
# Central Banks
# ==========================================================

def render_central_banks() -> None:

    st.subheader(
        "Central Bank Monitor"
    )

    rows = []

    for currency, data in (
        CENTRAL_BANKS.items()
    ):

        rows.append(
            {
                "currency": currency,
                "central_bank": data.get(
                    "bank"
                ),
                "policy_rate": data.get(
                    "rate"
                ),
                "hawkish_score": data.get(
                    "hawkish"
                ),
            }
        )

    df = pd.DataFrame(rows)

    _grid(
        df,
        "central_bank_monitor_grid",
    )

    fig = px.bar(
        df.sort_values(
            "policy_rate",
            ascending=False,
        ),
        x="currency",
        y="policy_rate",
        title="Policy Rates",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    fig2 = px.bar(
        df.sort_values(
            "hawkish_score",
            ascending=False,
        ),
        x="currency",
        y="hawkish_score",
        title="Hawkish Rankings",
    )

    st.plotly_chart(
        fig2,
        use_container_width=True,
    )


# ==========================================================
# History
# ==========================================================

def render_history(
    engine: ForexCentralBankEngine,
) -> None:

    st.subheader(
        "Policy History"
    )

    pair_filter = st.text_input(
        "Pair Filter",
        value="",
        key="cb_history_filter",
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
        "cb_history_grid",
    )

    if {
        "created_at",
        "central_bank_score",
    }.issubset(df.columns):

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=df["created_at"],
                y=df[
                    "central_bank_score"
                ],
                mode="lines+markers",
                name="Policy Score",
            )
        )

        fig.update_layout(
            title="Central Bank Trend"
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

    render_forex_central_bank_dashboard(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )