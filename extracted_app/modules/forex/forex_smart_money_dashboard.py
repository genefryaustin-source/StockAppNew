# modules/forex/forex_smart_money_dashboard.py

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
    from modules.forex.forex_order_flow_engine import (
        ForexOrderFlowEngine,
        get_forex_order_flow_engine,
    )
    from modules.forex.forex_liquidity_engine import (
        ForexLiquidityEngine,
        get_forex_liquidity_engine,
    )
    from modules.forex.forex_macro_engine import (
        ForexMacroEngine,
        get_forex_macro_engine,
    )
    from modules.forex.forex_recommendation_engine import (
        ForexRecommendationEngine,
        get_forex_recommendation_engine,
    )
    from modules.forex.forex_service import (
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )
except Exception:
    from forex_order_flow_engine import (
        ForexOrderFlowEngine,
        get_forex_order_flow_engine,
    )
    from forex_liquidity_engine import (
        ForexLiquidityEngine,
        get_forex_liquidity_engine,
    )
    from forex_macro_engine import (
        ForexMacroEngine,
        get_forex_macro_engine,
    )
    from forex_recommendation_engine import (
        ForexRecommendationEngine,
        get_forex_recommendation_engine,
    )
    from forex_service import (
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )


DEFAULT_PAIRS = MAJOR_PAIRS + CROSS_PAIRS


def _df(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _safe_numeric(
    df: pd.DataFrame,
    columns: List[str],
) -> pd.DataFrame:
    if df.empty:
        return df

    clean_df = df.copy()

    for col in columns:
        if col in clean_df.columns:
            clean_df[col] = pd.to_numeric(
                clean_df[col],
                errors="coerce",
            ).fillna(0)

    return clean_df


def _grid(
    df: pd.DataFrame,
    key: str,
    height: int = 575,
) -> None:
    if df.empty:
        st.info("No smart money data available.")
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


def _build_smart_money_matrix(
    *,
    flow_rows: List[Dict[str, Any]],
    liquidity_rows: List[Dict[str, Any]],
    macro_rows: List[Dict[str, Any]],
    recommendation_rows: List[Dict[str, Any]],
) -> pd.DataFrame:
    flow_df = _df(flow_rows)
    liquidity_df = _df(liquidity_rows)
    macro_df = _df(macro_rows)
    rec_df = _df(recommendation_rows)

    if flow_df.empty:
        return pd.DataFrame()

    cols = [
        "pair",
        "imbalance_score",
        "liquidity_score",
        "absorption_score",
        "sweep_score",
        "flow_direction",
        "flow_signal",
        "confidence_score",
        "asof",
    ]
    flow_df = flow_df[[c for c in cols if c in flow_df.columns]].copy()

    flow_df = flow_df.rename(
        columns={
            "confidence_score": "flow_confidence",
            "liquidity_score": "flow_liquidity_score",
            "asof": "flow_asof",
        }
    )

    if not liquidity_df.empty:
        liq_cols = [
            "pair",
            "tradability_score",
            "liquidity_score",
            "spread_bps",
            "liquidity_tier",
            "estimated_depth_score",
            "volume_proxy",
        ]
        liquidity_df = liquidity_df[
            [c for c in liq_cols if c in liquidity_df.columns]
        ].copy()
        liquidity_df = liquidity_df.rename(
            columns={
                "liquidity_score": "market_liquidity_score",
            }
        )
        matrix = pd.merge(
            flow_df,
            liquidity_df,
            on="pair",
            how="left",
        )
    else:
        matrix = flow_df.copy()

    if not macro_df.empty:
        macro_cols = [
            "pair",
            "macro_score",
            "confidence_score",
            "macro_direction",
            "macro_recommendation",
            "rate_differential",
            "growth_differential",
            "yield_signal",
        ]
        macro_df = macro_df[
            [c for c in macro_cols if c in macro_df.columns]
        ].copy()
        macro_df = macro_df.rename(
            columns={
                "confidence_score": "macro_confidence",
            }
        )
        matrix = pd.merge(
            matrix,
            macro_df,
            on="pair",
            how="left",
        )

    if not rec_df.empty:
        rec_cols = [
            "pair",
            "recommendation",
            "conviction_score",
            "confidence_score",
            "risk_reward",
            "risk_score",
        ]
        rec_df = rec_df[
            [c for c in rec_cols if c in rec_df.columns]
        ].copy()
        rec_df = rec_df.rename(
            columns={
                "confidence_score": "recommendation_confidence",
            }
        )
        matrix = pd.merge(
            matrix,
            rec_df,
            on="pair",
            how="left",
        )

    numeric_cols = [
        "imbalance_score",
        "flow_liquidity_score",
        "absorption_score",
        "sweep_score",
        "flow_confidence",
        "tradability_score",
        "market_liquidity_score",
        "spread_bps",
        "estimated_depth_score",
        "volume_proxy",
        "macro_score",
        "macro_confidence",
        "rate_differential",
        "growth_differential",
        "yield_signal",
        "conviction_score",
        "recommendation_confidence",
        "risk_reward",
        "risk_score",
    ]

    matrix = _safe_numeric(
        matrix,
        numeric_cols,
    )

    matrix["smart_money_score"] = (
        matrix.get("imbalance_score", 0) * 0.18
        + matrix.get("flow_confidence", 0) * 0.15
        + matrix.get("absorption_score", 0) * 0.12
        + matrix.get("sweep_score", 0) * 0.08
        + matrix.get("tradability_score", 0) * 0.12
        + matrix.get("market_liquidity_score", 0) * 0.10
        + matrix.get("macro_score", 0) * 0.12
        + matrix.get("macro_confidence", 0) * 0.05
        + matrix.get("conviction_score", 0) * 0.08
    )

    matrix["smart_money_direction"] = matrix.apply(
        _smart_money_direction,
        axis=1,
    )

    matrix["smart_money_signal"] = matrix.apply(
        _smart_money_signal,
        axis=1,
    )

    matrix["institutional_grade"] = matrix[
        "smart_money_score"
    ].apply(_institutional_grade)

    matrix = matrix.sort_values(
        by=[
            "smart_money_score",
            "flow_confidence",
            "tradability_score",
        ],
        ascending=False,
    )

    return matrix


def _smart_money_direction(row: pd.Series) -> str:
    flow_direction = str(
        row.get("flow_direction", "")
    ).upper()
    macro_direction = str(
        row.get("macro_direction", "")
    ).upper()
    rec = str(
        row.get("recommendation", "")
    ).upper()

    bullish_votes = 0
    bearish_votes = 0

    if flow_direction == "BULLISH":
        bullish_votes += 1
    elif flow_direction == "BEARISH":
        bearish_votes += 1

    if macro_direction == "BULLISH":
        bullish_votes += 1
    elif macro_direction == "BEARISH":
        bearish_votes += 1

    if rec in {
        "STRONG_BUY",
        "BUY",
    }:
        bullish_votes += 1
    elif rec in {
        "SELL",
        "STRONG_SELL",
    }:
        bearish_votes += 1

    if bullish_votes > bearish_votes:
        return "BULLISH"

    if bearish_votes > bullish_votes:
        return "BEARISH"

    return "NEUTRAL"


def _smart_money_signal(row: pd.Series) -> str:
    score = float(
        row.get("smart_money_score", 0)
    )
    direction = str(
        row.get("smart_money_direction", "")
    ).upper()
    sweep = float(
        row.get("sweep_score", 0)
    )
    absorption = float(
        row.get("absorption_score", 0)
    )

    if score >= 82 and direction == "BULLISH":
        return "INSTITUTIONAL_ACCUMULATION"

    if score >= 82 and direction == "BEARISH":
        return "INSTITUTIONAL_DISTRIBUTION"

    if sweep >= 70 and direction == "BULLISH":
        return "BUY_SIDE_SWEEP"

    if sweep >= 70 and direction == "BEARISH":
        return "SELL_SIDE_SWEEP"

    if absorption >= 70 and direction == "BULLISH":
        return "BUY_ABSORPTION"

    if absorption >= 70 and direction == "BEARISH":
        return "SELL_ABSORPTION"

    if score >= 65:
        return "SMART_MONEY_WATCH"

    return "NO_CLEAR_SMART_MONEY_EDGE"


def _institutional_grade(score: float) -> str:
    if score >= 85:
        return "A+"

    if score >= 78:
        return "A"

    if score >= 70:
        return "B"

    if score >= 60:
        return "C"

    return "D"


def render_forex_smart_money_dashboard(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    order_flow_engine: Optional[ForexOrderFlowEngine] = None,
    liquidity_engine: Optional[ForexLiquidityEngine] = None,
    macro_engine: Optional[ForexMacroEngine] = None,
    recommendation_engine: Optional[
        ForexRecommendationEngine
    ] = None,
) -> None:
    order_flow_engine = (
        order_flow_engine
        or get_forex_order_flow_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )
    )

    liquidity_engine = (
        liquidity_engine
        or get_forex_liquidity_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )
    )

    macro_engine = (
        macro_engine
        or get_forex_macro_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )
    )

    recommendation_engine = (
        recommendation_engine
        or get_forex_recommendation_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )
    )

    st.title("Forex Smart Money Dashboard")
    st.caption(
        "Institutional alignment across order flow, liquidity, macro, and recommendations."
    )

    workspace = st.radio(
        "Smart Money Workspace",
        [
            "Matrix",
            "Accumulation",
            "Distribution",
            "Signal Detail",
            "History Inputs",
        ],
        horizontal=True,
        key="forex_smart_money_workspace",
    )

    if workspace == "Matrix":
        render_matrix(
            order_flow_engine=order_flow_engine,
            liquidity_engine=liquidity_engine,
            macro_engine=macro_engine,
            recommendation_engine=recommendation_engine,
        )

    elif workspace == "Accumulation":
        render_accumulation()

    elif workspace == "Distribution":
        render_distribution()

    elif workspace == "Signal Detail":
        render_signal_detail()

    elif workspace == "History Inputs":
        render_history_inputs(
            order_flow_engine=order_flow_engine,
            liquidity_engine=liquidity_engine,
            macro_engine=macro_engine,
            recommendation_engine=recommendation_engine,
        )


def render_matrix(
    *,
    order_flow_engine: ForexOrderFlowEngine,
    liquidity_engine: ForexLiquidityEngine,
    macro_engine: ForexMacroEngine,
    recommendation_engine: ForexRecommendationEngine,
) -> None:
    st.subheader("Smart Money Matrix")

    col1, col2, col3 = st.columns(3)

    pair_group = col1.selectbox(
        "Pair Universe",
        [
            "Major Pairs",
            "Cross Pairs",
            "All",
        ],
        key="smart_money_pair_group",
    )

    min_score = col2.slider(
        "Minimum Smart Money Score",
        min_value=0,
        max_value=100,
        value=0,
        step=1,
        key="smart_money_min_score",
    )

    save_inputs = col3.checkbox(
        "Save Source Scans",
        value=True,
        key="smart_money_save_source_scans",
    )

    pairs = (
        MAJOR_PAIRS
        if pair_group == "Major Pairs"
        else CROSS_PAIRS
        if pair_group == "Cross Pairs"
        else DEFAULT_PAIRS
    )

    if st.button(
        "Build Smart Money Matrix",
        key="smart_money_build_matrix",
        use_container_width=True,
    ):
        with st.spinner("Building institutional smart money matrix..."):
            flow_scan = order_flow_engine.scan_pairs(
                pairs=pairs,
                save=save_inputs,
            )
            liquidity_scan = liquidity_engine.scan_pairs(
                pairs=pairs,
                save=save_inputs,
            )
            macro_scan = macro_engine.scan_pairs(
                pairs=pairs,
                save=save_inputs,
            )
            recommendation_scan = recommendation_engine.run_scan(
                pairs=pairs,
                save=save_inputs,
            )

            matrix = _build_smart_money_matrix(
                flow_rows=flow_scan.snapshots,
                liquidity_rows=liquidity_scan.snapshots,
                macro_rows=macro_scan.snapshots,
                recommendation_rows=recommendation_scan.recommendations,
            )

            if not matrix.empty:
                matrix = matrix[
                    matrix["smart_money_score"] >= float(min_score)
                ]

            st.session_state[
                "forex_smart_money_matrix"
            ] = matrix.to_dict(
                orient="records"
            )

    matrix_df = _df(
        st.session_state.get(
            "forex_smart_money_matrix",
            [],
        )
    )

    if matrix_df.empty:
        st.info("Build the Smart Money Matrix.")
        return

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Pairs",
        len(matrix_df),
    )
    c2.metric(
        "Avg Score",
        round(
            matrix_df[
                "smart_money_score"
            ].mean(),
            2,
        ),
    )
    c3.metric(
        "Bullish",
        int(
            (
                matrix_df[
                    "smart_money_direction"
                ]
                == "BULLISH"
            ).sum()
        ),
    )
    c4.metric(
        "Bearish",
        int(
            (
                matrix_df[
                    "smart_money_direction"
                ]
                == "BEARISH"
            ).sum()
        ),
    )
    c5.metric(
        "Top Pair",
        matrix_df.iloc[0]["pair"],
    )

    st.divider()

    display_cols = [
        c
        for c in [
            "pair",
            "smart_money_score",
            "institutional_grade",
            "smart_money_direction",
            "smart_money_signal",
            "flow_direction",
            "flow_signal",
            "imbalance_score",
            "flow_confidence",
            "tradability_score",
            "market_liquidity_score",
            "macro_direction",
            "macro_score",
            "macro_confidence",
            "recommendation",
            "conviction_score",
            "risk_reward",
        ]
        if c in matrix_df.columns
    ]

    _grid(
        matrix_df[display_cols],
        "smart_money_matrix_grid",
    )

    fig = px.scatter(
        matrix_df,
        x="smart_money_score",
        y="conviction_score"
        if "conviction_score" in matrix_df.columns
        else "flow_confidence",
        color="smart_money_direction",
        size="tradability_score"
        if "tradability_score" in matrix_df.columns
        else None,
        hover_name="pair",
        title="Smart Money Score vs Conviction",
    )
    st.plotly_chart(
        fig,
        use_container_width=True,
    )


def render_accumulation() -> None:
    st.subheader("Accumulation Signals")

    matrix_df = _df(
        st.session_state.get(
            "forex_smart_money_matrix",
            [],
        )
    )

    if matrix_df.empty:
        st.info("Build the Smart Money Matrix first.")
        return

    accum_df = matrix_df[
        matrix_df[
            "smart_money_signal"
        ].isin(
            [
                "INSTITUTIONAL_ACCUMULATION",
                "BUY_SIDE_SWEEP",
                "BUY_ABSORPTION",
                "SMART_MONEY_WATCH",
            ]
        )
        & (
            matrix_df[
                "smart_money_direction"
            ]
            == "BULLISH"
        )
    ].sort_values(
        "smart_money_score",
        ascending=False,
    )

    _grid(
        accum_df,
        "smart_money_accumulation_grid",
    )

    if not accum_df.empty:
        fig = px.bar(
            accum_df.head(25),
            x="pair",
            y="smart_money_score",
            color="smart_money_signal",
            title="Accumulation Ranking",
        )
        st.plotly_chart(
            fig,
            use_container_width=True,
        )


def render_distribution() -> None:
    st.subheader("Distribution Signals")

    matrix_df = _df(
        st.session_state.get(
            "forex_smart_money_matrix",
            [],
        )
    )

    if matrix_df.empty:
        st.info("Build the Smart Money Matrix first.")
        return

    dist_df = matrix_df[
        matrix_df[
            "smart_money_signal"
        ].isin(
            [
                "INSTITUTIONAL_DISTRIBUTION",
                "SELL_SIDE_SWEEP",
                "SELL_ABSORPTION",
                "SMART_MONEY_WATCH",
            ]
        )
        & (
            matrix_df[
                "smart_money_direction"
            ]
            == "BEARISH"
        )
    ].sort_values(
        "smart_money_score",
        ascending=False,
    )

    _grid(
        dist_df,
        "smart_money_distribution_grid",
    )

    if not dist_df.empty:
        fig = px.bar(
            dist_df.head(25),
            x="pair",
            y="smart_money_score",
            color="smart_money_signal",
            title="Distribution Ranking",
        )
        st.plotly_chart(
            fig,
            use_container_width=True,
        )


def render_signal_detail() -> None:
    st.subheader("Smart Money Signal Detail")

    matrix_df = _df(
        st.session_state.get(
            "forex_smart_money_matrix",
            [],
        )
    )

    if matrix_df.empty:
        st.info("Build the Smart Money Matrix first.")
        return

    pair = st.selectbox(
        "Signal Pair",
        matrix_df["pair"].tolist(),
        key="smart_money_signal_pair",
    )

    row = matrix_df[
        matrix_df["pair"] == pair
    ].iloc[0]

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Smart Money Score",
        round(
            float(
                row.get(
                    "smart_money_score",
                    0,
                )
            ),
            2,
        ),
    )
    c2.metric(
        "Grade",
        row.get(
            "institutional_grade",
            "-",
        ),
    )
    c3.metric(
        "Direction",
        row.get(
            "smart_money_direction",
            "-",
        ),
    )
    c4.metric(
        "Signal",
        row.get(
            "smart_money_signal",
            "-",
        ),
    )

    factor_cols = [
        "imbalance_score",
        "flow_confidence",
        "absorption_score",
        "sweep_score",
        "tradability_score",
        "market_liquidity_score",
        "macro_score",
        "macro_confidence",
        "conviction_score",
    ]

    factor_df = pd.DataFrame(
        [
            {
                "factor": col.replace(
                    "_",
                    " ",
                ).title(),
                "score": float(
                    row.get(
                        col,
                        0,
                    )
                ),
            }
            for col in factor_cols
            if col in row
        ]
    )

    fig = px.bar(
        factor_df,
        x="factor",
        y="score",
        title=f"{pair} Smart Money Factor Breakdown",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    st.json(
        row.to_dict()
    )


def render_history_inputs(
    *,
    order_flow_engine: ForexOrderFlowEngine,
    liquidity_engine: ForexLiquidityEngine,
    macro_engine: ForexMacroEngine,
    recommendation_engine: ForexRecommendationEngine,
) -> None:
    st.subheader("Smart Money Source Inputs")

    workspace = st.radio(
        "Smart Money Source Workspace",
        [
            "Order Flow",
            "Liquidity",
            "Macro",
            "Recommendations",
        ],
        horizontal=True,
        key="smart_money_source_workspace",
    )

    if workspace == "Order Flow":
        rows = order_flow_engine.load_snapshots(
            limit=1000,
        )

    elif workspace == "Liquidity":
        rows = liquidity_engine.load_snapshots(
            limit=1000,
        )

    elif workspace == "Macro":
        rows = macro_engine.load_snapshots(
            limit=1000,
        )

    else:
        rows = recommendation_engine.load_recommendations(
            status="ALL",
            limit=1000,
        )

    _grid(
        _df(rows),
        f"smart_money_source_{workspace}",
    )


def render(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
) -> None:
    render_forex_smart_money_dashboard(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )