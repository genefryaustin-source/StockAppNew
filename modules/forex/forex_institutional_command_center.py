# modules/forex/forex_institutional_command_center.py

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
    from modules.forex.forex_service import MAJOR_PAIRS, CROSS_PAIRS
    from modules.forex.forex_workstation import render_forex_workstation
    from modules.forex.forex_dealer_dashboard import render_forex_dealer_dashboard
    from modules.forex.forex_smart_money_dashboard import render_forex_smart_money_dashboard
    from modules.forex.forex_order_flow_dashboard import render_forex_order_flow_dashboard
    from modules.forex.forex_macro_dashboard import render_forex_macro_dashboard
    from modules.forex.forex_liquidity_dashboard import render_forex_liquidity_dashboard
    from modules.forex.forex_execution_quality_dashboard import render_forex_execution_quality_dashboard
    from modules.forex.forex_recommendation_dashboard import render_forex_recommendation_dashboard
    from modules.forex.forex_attribution_dashboard import render_forex_attribution_dashboard
    from modules.forex.forex_risk_dashboard import render_forex_risk_dashboard
    from modules.forex.forex_execution_dashboard import render_forex_execution_dashboard
    from modules.forex.forex_validation_dashboard import render_forex_validation_dashboard

    from modules.forex.forex_order_flow_engine import get_forex_order_flow_engine
    from modules.forex.forex_liquidity_engine import get_forex_liquidity_engine
    from modules.forex.forex_macro_engine import get_forex_macro_engine
    from modules.forex.forex_recommendation_engine import get_forex_recommendation_engine
except Exception:
    from forex_service import MAJOR_PAIRS, CROSS_PAIRS
    from forex_workstation import render_forex_workstation
    from forex_dealer_dashboard import render_forex_dealer_dashboard
    from forex_smart_money_dashboard import render_forex_smart_money_dashboard
    from forex_order_flow_dashboard import render_forex_order_flow_dashboard
    from forex_macro_dashboard import render_forex_macro_dashboard
    from forex_liquidity_dashboard import render_forex_liquidity_dashboard
    from forex_execution_quality_dashboard import render_forex_execution_quality_dashboard
    from forex_recommendation_dashboard import render_forex_recommendation_dashboard
    from forex_attribution_dashboard import render_forex_attribution_dashboard
    from forex_risk_dashboard import render_forex_risk_dashboard
    from forex_execution_dashboard import render_forex_execution_dashboard
    from forex_validation_dashboard import render_forex_validation_dashboard

    from forex_order_flow_engine import get_forex_order_flow_engine
    from forex_liquidity_engine import get_forex_liquidity_engine
    from forex_macro_engine import get_forex_macro_engine
    from forex_recommendation_engine import get_forex_recommendation_engine


DEFAULT_PAIRS = MAJOR_PAIRS + CROSS_PAIRS


def _df(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _grid(df: pd.DataFrame, key: str, height: int = 550) -> None:
    if df.empty:
        st.info("No institutional Forex data available.")
        return

    if HAS_AGGRID:
        builder = GridOptionsBuilder.from_dataframe(df)
        builder.configure_default_column(sortable=True, filter=True, resizable=True)
        builder.configure_pagination(enabled=True, paginationPageSize=25)
        builder.configure_side_bar()
        AgGrid(
            df,
            gridOptions=builder.build(),
            fit_columns_on_grid_load=False,
            height=height,
            key=key,
        )
    else:
        st.dataframe(df, use_container_width=True, hide_index=True, height=height)


def _safe_render(renderer: Any, **kwargs: Any) -> None:
    if renderer is None:
        st.warning("Dashboard unavailable.")
        return

    try:
        renderer(**kwargs)
    except Exception as exc:
        st.error(f"Dashboard failed to load: {exc}")


def _build_institutional_snapshot(
    *,
    tenant_id: Optional[str],
    user_id: Optional[str],
    portfolio_id: Optional[str],
    db: Any,
    pair_group: str,
    save: bool,
) -> Dict[str, Any]:
    order_flow_engine = get_forex_order_flow_engine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )
    liquidity_engine = get_forex_liquidity_engine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )
    macro_engine = get_forex_macro_engine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )
    recommendation_engine = get_forex_recommendation_engine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )

    if pair_group == "Major Pairs":
        pairs = MAJOR_PAIRS
    elif pair_group == "Cross Pairs":
        pairs = CROSS_PAIRS
    else:
        pairs = DEFAULT_PAIRS

    flow_scan = order_flow_engine.scan_pairs(pairs=pairs, save=save)
    liquidity_scan = liquidity_engine.scan_pairs(pairs=pairs, save=save)
    macro_scan = macro_engine.scan_pairs(pairs=pairs, save=save)
    recommendation_scan = recommendation_engine.run_scan(pairs=pairs, save=save)

    flow_df = _df(flow_scan.snapshots)
    liq_df = _df(liquidity_scan.snapshots)
    macro_df = _df(macro_scan.snapshots)
    rec_df = _df(recommendation_scan.recommendations)

    if flow_df.empty:
        matrix = pd.DataFrame()
    else:
        flow_cols = [
            "pair",
            "imbalance_score",
            "flow_direction",
            "flow_signal",
            "confidence_score",
            "absorption_score",
            "sweep_score",
        ]
        matrix = flow_df[[c for c in flow_cols if c in flow_df.columns]].copy()
        matrix = matrix.rename(columns={"confidence_score": "flow_confidence"})

        if not liq_df.empty:
            liq_cols = [
                "pair",
                "liquidity_score",
                "tradability_score",
                "spread_bps",
                "liquidity_tier",
            ]
            liq_df = liq_df[[c for c in liq_cols if c in liq_df.columns]].copy()
            matrix = pd.merge(matrix, liq_df, on="pair", how="left")

        if not macro_df.empty:
            macro_cols = [
                "pair",
                "macro_score",
                "confidence_score",
                "macro_direction",
                "macro_recommendation",
            ]
            macro_df = macro_df[[c for c in macro_cols if c in macro_df.columns]].copy()
            macro_df = macro_df.rename(columns={"confidence_score": "macro_confidence"})
            matrix = pd.merge(matrix, macro_df, on="pair", how="left")

        if not rec_df.empty:
            rec_cols = [
                "pair",
                "recommendation",
                "conviction_score",
                "confidence_score",
                "risk_reward",
            ]
            rec_df = rec_df[[c for c in rec_cols if c in rec_df.columns]].copy()
            rec_df = rec_df.rename(columns={"confidence_score": "recommendation_confidence"})
            matrix = pd.merge(matrix, rec_df, on="pair", how="left")

        numeric_cols = [
            "imbalance_score",
            "flow_confidence",
            "absorption_score",
            "sweep_score",
            "liquidity_score",
            "tradability_score",
            "spread_bps",
            "macro_score",
            "macro_confidence",
            "conviction_score",
            "recommendation_confidence",
            "risk_reward",
        ]
        for col in numeric_cols:
            if col in matrix.columns:
                matrix[col] = pd.to_numeric(matrix[col], errors="coerce").fillna(0)

        matrix["institutional_score"] = (
            matrix.get("imbalance_score", 0) * 0.14
            + matrix.get("flow_confidence", 0) * 0.12
            + matrix.get("absorption_score", 0) * 0.10
            + matrix.get("sweep_score", 0) * 0.08
            + matrix.get("liquidity_score", 0) * 0.12
            + matrix.get("tradability_score", 0) * 0.10
            + matrix.get("macro_score", 0) * 0.12
            + matrix.get("macro_confidence", 0) * 0.07
            + matrix.get("conviction_score", 0) * 0.10
            + matrix.get("recommendation_confidence", 0) * 0.05
        )

        matrix["institutional_direction"] = matrix.apply(
            _institutional_direction,
            axis=1,
        )
        matrix["institutional_signal"] = matrix.apply(
            _institutional_signal,
            axis=1,
        )
        matrix = matrix.sort_values("institutional_score", ascending=False)

    return {
        "pair_count": len(pairs),
        "flow_scan": flow_scan.to_dict(),
        "liquidity_scan": liquidity_scan.to_dict(),
        "macro_scan": macro_scan.to_dict(),
        "recommendation_scan": recommendation_scan.to_dict(),
        "matrix": matrix.to_dict(orient="records") if not matrix.empty else [],
    }


def _institutional_direction(row: pd.Series) -> str:
    bullish = 0
    bearish = 0

    if str(row.get("flow_direction", "")).upper() == "BULLISH":
        bullish += 1
    elif str(row.get("flow_direction", "")).upper() == "BEARISH":
        bearish += 1

    if str(row.get("macro_direction", "")).upper() == "BULLISH":
        bullish += 1
    elif str(row.get("macro_direction", "")).upper() == "BEARISH":
        bearish += 1

    rec = str(row.get("recommendation", "")).upper()
    if rec in {"STRONG_BUY", "BUY"}:
        bullish += 1
    elif rec in {"SELL", "STRONG_SELL"}:
        bearish += 1

    if bullish > bearish:
        return "BULLISH"
    if bearish > bullish:
        return "BEARISH"
    return "NEUTRAL"


def _institutional_signal(row: pd.Series) -> str:
    score = float(row.get("institutional_score", 0))
    direction = str(row.get("institutional_direction", "NEUTRAL")).upper()
    flow_signal = str(row.get("flow_signal", "")).upper()
    macro_rec = str(row.get("macro_recommendation", "")).upper()
    rec = str(row.get("recommendation", "")).upper()

    if score >= 85 and direction == "BULLISH":
        return "INSTITUTIONAL_LONG_CONVICTION"
    if score >= 85 and direction == "BEARISH":
        return "INSTITUTIONAL_SHORT_CONVICTION"
    if "AGGRESSIVE_BUY" in flow_signal and rec in {"BUY", "STRONG_BUY"}:
        return "FLOW_CONFIRMED_LONG"
    if "AGGRESSIVE_SELL" in flow_signal and rec in {"SELL", "STRONG_SELL"}:
        return "FLOW_CONFIRMED_SHORT"
    if macro_rec in {"STRONG_BUY", "BUY"} and direction == "BULLISH":
        return "MACRO_CONFIRMED_LONG"
    if macro_rec in {"SELL", "STRONG_SELL"} and direction == "BEARISH":
        return "MACRO_CONFIRMED_SHORT"
    if score >= 65:
        return "INSTITUTIONAL_WATCH"
    return "NO_EDGE"


def render_forex_institutional_command_center(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
) -> None:
    st.title("Forex Institutional Command Center")
    st.caption("Institutional workstation, dealer intelligence, smart money, order flow, liquidity, macro, execution, attribution, and validation.")

    workspace = st.radio(
        "Institutional Command Workspace",
        [
            "Overview",
            "Workstation",
            "Dealer",
            "Smart Money",
            "Order Flow",
            "Macro",
            "Liquidity",
            "Execution",
            "Risk",
            "Validation",
        ],
        horizontal=True,
        key="forex_institutional_command_workspace",
    )

    if workspace == "Overview":
        render_overview(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )

    elif workspace == "Workstation":
        _safe_render(
            render_forex_workstation,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )

    elif workspace == "Dealer":
        _safe_render(
            render_forex_dealer_dashboard,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )

    elif workspace == "Smart Money":
        _safe_render(
            render_forex_smart_money_dashboard,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )

    elif workspace == "Order Flow":
        _safe_render(
            render_forex_order_flow_dashboard,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )

    elif workspace == "Macro":
        _safe_render(
            render_forex_macro_dashboard,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )

    elif workspace == "Liquidity":
        _safe_render(
            render_forex_liquidity_dashboard,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )

    elif workspace == "Execution":
        render_execution_cluster(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )

    elif workspace == "Risk":
        _safe_render(
            render_forex_risk_dashboard,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )

    elif workspace == "Validation":
        _safe_render(
            render_forex_validation_dashboard,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )


def render_overview(
    *,
    tenant_id: Optional[str],
    user_id: Optional[str],
    portfolio_id: Optional[str],
    db: Any,
) -> None:
    st.subheader("Institutional Forex Overview")

    c1, c2, c3 = st.columns(3)

    pair_group = c1.selectbox(
        "Institutional Pair Universe",
        ["Major Pairs", "Cross Pairs", "All Pairs"],
        key="institutional_pair_universe",
    )

    save_inputs = c2.checkbox(
        "Save Source Scans",
        value=True,
        key="institutional_save_scans",
    )

    min_score = c3.slider(
        "Minimum Institutional Score",
        min_value=0,
        max_value=100,
        value=0,
        key="institutional_min_score",
    )

    if st.button(
        "Run Institutional Forex Snapshot",
        key="institutional_snapshot_btn",
        use_container_width=True,
    ):
        with st.spinner("Running institutional Forex snapshot..."):
            snapshot = _build_institutional_snapshot(
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=portfolio_id,
                db=db,
                pair_group=pair_group,
                save=save_inputs,
            )
            matrix = _df(snapshot.get("matrix", []))
            if not matrix.empty:
                matrix = matrix[matrix["institutional_score"] >= float(min_score)]
                snapshot["matrix"] = matrix.to_dict(orient="records")

            st.session_state["forex_institutional_snapshot"] = snapshot

    snapshot = st.session_state.get("forex_institutional_snapshot")

    if not snapshot:
        st.info("Run the institutional snapshot.")
        return

    matrix_df = _df(snapshot.get("matrix", []))

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Pairs", snapshot.get("pair_count", 0))
    c2.metric("Matrix Rows", len(matrix_df))
    c3.metric("Flow Bullish", snapshot.get("flow_scan", {}).get("bullish_count", 0))
    c4.metric("Macro Bullish", snapshot.get("macro_scan", {}).get("bullish_count", 0))
    c5.metric("Top Pair", matrix_df.iloc[0]["pair"] if not matrix_df.empty else "-")

    if matrix_df.empty:
        st.info("No matrix rows passed the selected filters.")
        return

    st.divider()

    display_cols = [
        c for c in [
            "pair",
            "institutional_score",
            "institutional_direction",
            "institutional_signal",
            "flow_direction",
            "flow_signal",
            "imbalance_score",
            "flow_confidence",
            "liquidity_score",
            "tradability_score",
            "macro_direction",
            "macro_score",
            "macro_confidence",
            "recommendation",
            "conviction_score",
            "risk_reward",
        ]
        if c in matrix_df.columns
    ]

    _grid(matrix_df[display_cols], "institutional_overview_matrix")

    c1, c2 = st.columns(2)

    with c1:
        if "institutional_direction" in matrix_df.columns:
            direction_df = (
                matrix_df.groupby("institutional_direction")
                .size()
                .reset_index(name="count")
            )
            fig = px.pie(
                direction_df,
                names="institutional_direction",
                values="count",
                title="Institutional Direction",
            )
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        if {"institutional_score", "conviction_score", "pair"}.issubset(matrix_df.columns):
            fig = px.scatter(
                matrix_df,
                x="institutional_score",
                y="conviction_score",
                color="institutional_direction",
                size="tradability_score" if "tradability_score" in matrix_df.columns else None,
                hover_name="pair",
                title="Institutional Score vs Conviction",
            )
            st.plotly_chart(fig, use_container_width=True)


def render_execution_cluster(
    *,
    tenant_id: Optional[str],
    user_id: Optional[str],
    portfolio_id: Optional[str],
    db: Any,
) -> None:
    execution_workspace = st.radio(
        "Institutional Execution Workspace",
        ["Execution Center", "Execution Quality", "Attribution", "Recommendations"],
        horizontal=True,
        key="institutional_execution_workspace",
    )

    if execution_workspace == "Execution Center":
        _safe_render(
            render_forex_execution_dashboard,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )

    elif execution_workspace == "Execution Quality":
        _safe_render(
            render_forex_execution_quality_dashboard,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )

    elif execution_workspace == "Attribution":
        _safe_render(
            render_forex_attribution_dashboard,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )

    elif execution_workspace == "Recommendations":
        _safe_render(
            render_forex_recommendation_dashboard,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )


def render(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
) -> None:
    render_forex_institutional_command_center(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )