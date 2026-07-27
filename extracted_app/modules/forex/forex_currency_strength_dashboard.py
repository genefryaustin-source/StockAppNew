# modules/forex/forex_currency_strength_dashboard.py

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
    from modules.forex.forex_currency_strength_engine import (
        ForexCurrencyStrengthEngine,
        get_forex_currency_strength_engine,
        MAJOR_CURRENCIES,
    )

except Exception:

    from forex_currency_strength_engine import (
        ForexCurrencyStrengthEngine,
        get_forex_currency_strength_engine,
        MAJOR_CURRENCIES,
    )


# =========================================================
# Helpers
# =========================================================

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
            "No currency strength data available."
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


# =========================================================
# Main Dashboard
# =========================================================

def render_forex_currency_strength_dashboard(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    engine: Optional[
        ForexCurrencyStrengthEngine
    ] = None,
) -> None:

    engine = (
        engine
        or get_forex_currency_strength_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )
    )

    st.title(
        "Forex Currency Strength Dashboard"
    )

    st.caption(
        "Global Currency Rankings • Relative Strength • Capital Rotation Intelligence"
    )

    workspace = st.radio(
        "Currency Strength Workspace",
        [
            "Currency Scanner",
            "Currency Analysis",
            "Strength Matrix",
            "Currency Rankings",
            "History",
        ],
        horizontal=True,
        key="currency_strength_workspace",
    )

    if workspace == "Currency Scanner":
        render_scanner(engine)

    elif workspace == "Currency Analysis":
        render_currency_analysis(engine)

    elif workspace == "Strength Matrix":
        render_strength_matrix(engine)

    elif workspace == "Currency Rankings":
        render_rankings(engine)

    elif workspace == "History":
        render_history(engine)


# =========================================================
# Scanner
# =========================================================

def render_scanner(
    engine: ForexCurrencyStrengthEngine,
) -> None:

    st.subheader(
        "Institutional Currency Scanner"
    )

    save_scan = st.checkbox(
        "Save Scan",
        value=True,
        key="currency_strength_save_scan",
    )

    if st.button(
        "Run Currency Strength Scan",
        use_container_width=True,
        key="run_currency_strength_scan",
    ):

        with st.spinner(
            "Analyzing global currency strength..."
        ):

            scan = engine.scan_currencies(
                save=save_scan,
            )

            st.session_state[
                "currency_strength_scan"
            ] = scan.to_dict()

    scan = st.session_state.get(
        "currency_strength_scan"
    )

    if not scan:
        st.info(
            "Run a currency strength scan."
        )
        return

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Currencies",
        scan.get(
            "currency_count",
            0,
        ),
    )

    c2.metric(
        "Strongest",
        scan.get(
            "strongest_currency",
            "",
        ),
    )

    c3.metric(
        "Weakest",
        scan.get(
            "weakest_currency",
            "",
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
            "currency",
            "global_strength_score",
            "percentile_rank",
            "strength_regime",
            "strength_signal",
            "confidence_score",
        ]
        if c in df.columns
    ]

    _grid(
        df[cols]
        if not df.empty
        else df,
        "currency_strength_scan_grid",
    )


# =========================================================
# Currency Analysis
# =========================================================

def render_currency_analysis(
    engine: ForexCurrencyStrengthEngine,
) -> None:

    st.subheader(
        "Currency Analysis"
    )

    currency = st.selectbox(
        "Currency",
        MAJOR_CURRENCIES,
        key="currency_strength_analysis",
    )

    if st.button(
        "Analyze Currency",
        use_container_width=True,
        key="analyze_currency_strength",
    ):

        snapshot = (
            engine.analyze_currency(
                currency,
                save=False,
            )
        )

        st.session_state[
            "currency_strength_snapshot"
        ] = snapshot.to_dict()

    snapshot = st.session_state.get(
        "currency_strength_snapshot"
    )

    if not snapshot:
        st.info(
            "Analyze a currency."
        )
        return

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Global Strength",
        snapshot.get(
            "global_strength_score",
            0,
        ),
    )

    c2.metric(
        "Relative",
        snapshot.get(
            "relative_strength_score",
            0,
        ),
    )

    c3.metric(
        "Macro",
        snapshot.get(
            "macro_strength_score",
            0,
        ),
    )

    c4.metric(
        "Flow",
        snapshot.get(
            "capital_flow_score",
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
                "Factor": "Relative",
                "Value": snapshot.get(
                    "relative_strength_score",
                    0,
                ),
            },
            {
                "Factor": "Macro",
                "Value": snapshot.get(
                    "macro_strength_score",
                    0,
                ),
            },
            {
                "Factor": "Flow",
                "Value": snapshot.get(
                    "capital_flow_score",
                    0,
                ),
            },
            {
                "Factor": "Momentum",
                "Value": snapshot.get(
                    "momentum_score",
                    0,
                ),
            },
            {
                "Factor": "Conviction",
                "Value": snapshot.get(
                    "conviction_score",
                    0,
                ),
            },
        ]
    )

    fig = px.bar(
        chart_df,
        x="Factor",
        y="Value",
        title=f"{currency} Strength Factors",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    st.json(snapshot)


# =========================================================
# Matrix
# =========================================================

def render_strength_matrix(
    engine: ForexCurrencyStrengthEngine,
) -> None:

    st.subheader(
        "Currency Strength Matrix"
    )

    rows = engine.load_snapshots(
        limit=5000,
    )

    df = _df(rows)

    if df.empty:
        st.info(
            "No strength history available."
        )
        return

    if {
        "global_strength_score",
        "confidence_score",
    }.issubset(df.columns):

        fig = px.scatter(
            df,
            x="global_strength_score",
            y="confidence_score",
            color="strength_regime",
            size="conviction_score",
            hover_name="currency",
            title="Currency Strength Matrix",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    _grid(
        df,
        "currency_strength_matrix_grid",
    )


# =========================================================
# Rankings
# =========================================================

def render_rankings(
    engine: ForexCurrencyStrengthEngine,
) -> None:

    st.subheader(
        "Global Currency Rankings"
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

    latest = (
        df.sort_values(
            "global_strength_score",
            ascending=False,
        )
        .head(20)
    )

    fig = px.bar(
        latest,
        x="currency",
        y="global_strength_score",
        color="strength_regime",
        title="Global Currency Strength Ranking",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    fig2 = px.bar(
        latest,
        x="currency",
        y="confidence_score",
        color="strength_regime",
        title="Currency Confidence Ranking",
    )

    st.plotly_chart(
        fig2,
        use_container_width=True,
    )


# =========================================================
# History
# =========================================================

def render_history(
    engine: ForexCurrencyStrengthEngine,
) -> None:

    st.subheader(
        "Currency Strength History"
    )

    currency = st.selectbox(
        "Currency Filter",
        ["ALL"] + MAJOR_CURRENCIES,
        key="currency_history_filter",
    )

    rows = engine.load_snapshots(
        currency=(
            None
            if currency == "ALL"
            else currency
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
        "currency_strength_history_grid",
    )

    if {
        "created_at",
        "global_strength_score",
    }.issubset(df.columns):

        fig = go.Figure()

        for curr in (
            df["currency"]
            .dropna()
            .unique()
        ):

            subset = (
                df[
                    df["currency"]
                    == curr
                ]
            )

            fig.add_trace(
                go.Scatter(
                    x=subset[
                        "created_at"
                    ],
                    y=subset[
                        "global_strength_score"
                    ],
                    mode="lines+markers",
                    name=curr,
                )
            )

        fig.update_layout(
            title="Currency Strength Trend"
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )


# =========================================================
# Public Entry Point
# =========================================================

def render(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
) -> None:

    render_forex_currency_strength_dashboard(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )