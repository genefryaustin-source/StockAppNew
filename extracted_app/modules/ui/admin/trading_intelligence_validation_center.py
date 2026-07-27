from __future__ import annotations

import traceback
import streamlit as st

from modules.trading_intelligence.trade_management_engine import TradeManagementEngine
from modules.trading_intelligence.recommendation_performance_engine import RecommendationPerformanceEngine
from modules.trading_intelligence.trade_attribution_engine import TradeAttributionEngine
from modules.trading_intelligence.portfolio_risk_monitor import PortfolioRiskMonitor
from modules.trading_intelligence.recommendation_command_center import RecommendationCommandCenter
from modules.trading_intelligence.recommendation_autopilot_engine import RecommendationAutopilotEngine
from modules.trading_intelligence.recommendation_lifecycle_engine import RecommendationLifecycleEngine
from modules.trading_intelligence.recommendation_alert_center import RecommendationAlertCenter
from modules.trading_intelligence.recommendation_target_tracking_engine import RecommendationTargetTrackingEngine
from modules.trading_intelligence.recommendation_stop_loss_monitor import RecommendationStopLossMonitor

from modules.trading_intelligence.trade_management_ui import render_trade_management_ui
from modules.trading_intelligence.recommendation_performance_ui import render_recommendation_performance_ui
from modules.trading_intelligence.trade_attribution_ui import render_trade_attribution_ui
from modules.trading_intelligence.portfolio_risk_dashboard import render_portfolio_risk_dashboard
from modules.trading_intelligence.recommendation_command_center_dashboard import (
    render_recommendation_command_center_dashboard,
)
from modules.trading_intelligence.recommendation_autopilot_dashboard import (
    render_recommendation_autopilot_dashboard,
)
from modules.trading_intelligence.recommendation_lifecycle_dashboard import (
    render_recommendation_lifecycle_dashboard,
)
from modules.trading_intelligence.recommendation_alert_center_dashboard import (
    render_recommendation_alert_center_dashboard,
)


def _reset_failed_transaction(db) -> None:
    try:
        db.rollback()
    except Exception:
        pass


def _safe_render(title: str, fn, *args, **kwargs) -> None:
    db = kwargs.get("db")

    try:
        _reset_failed_transaction(db)
        fn(*args, **kwargs)

    except Exception as e:
        _reset_failed_transaction(db)
        st.error(f"{title} failed:\n\n{e}")
        st.code(traceback.format_exc())


def _record_result(results, component: str, status: str, rows=0, error: str | None = None):
    results.append(
        {
            "Component": component,
            "Status": status,
            "Rows": rows,
            "Error": error or "",
        }
    )


def _run_validation_step(
    db,
    results,
    component: str,
    runner,
    rows_getter=None,
):
    try:
        _reset_failed_transaction(db)

        payload = runner()

        rows = 1
        if rows_getter is not None:
            rows = rows_getter(payload)

        status = "PASS"
        error = ""

        if isinstance(payload, dict) and payload.get("success") is False:
            status = "FAIL"
            error = payload.get("error", "")

        _record_result(results, component, status, rows, error)

        if status == "PASS":
            st.success(f"{component} PASS ({rows} rows)")
        else:
            st.error(f"{component} FAILED\n\n{error}")

        if hasattr(payload, "to_dict"):
            st.json(payload.to_dict())
        elif hasattr(payload, "head"):
            st.dataframe(
                payload.head(25),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.json(payload)

    except Exception as e:
        _reset_failed_transaction(db)
        _record_result(results, component, "FAIL", 0, str(e))
        st.error(f"{component} FAILED\n\n{e}")
        st.code(traceback.format_exc())


def render_trading_intelligence_validation_center(
    db,
    portfolio_id: str,
    user=None,
    **kwargs,
):
    _reset_failed_transaction(db)

    st.title("🧪 Trading Intelligence Validation Center")

    st.info(
        """
        This workspace validates the full Trading Intelligence stack:

        • Recommendation Command Center
        • Recommendation Autopilot
        • Lifecycle Engine
        • Target Tracking
        • Stop-Loss Monitoring
        • Alert Center
        • Trade Management
        • Recommendation Performance
        • Trade Attribution
        • Portfolio Risk
        """
    )

    if not portfolio_id:
        st.warning("No portfolio_id was provided.")
        return

    tabs = st.tabs(
        [
            "Engine Validation",
            "Command Center",
            "Autopilot",
            "Lifecycle",
            "Alerts",
            "Trade Management",
            "Performance",
            "Attribution",
            "Portfolio Risk",
        ]
    )

    with tabs[0]:
        st.subheader("Engine Validation")

        if st.button(
            "Run Full Validation",
            key="run_trading_intelligence_validation",
        ):
            results = []

            _run_validation_step(
                db,
                results,
                "TradeManagementEngine",
                lambda: TradeManagementEngine(db).get_trade_management_dataframe(portfolio_id),
                lambda payload: len(payload),
            )

            _run_validation_step(
                db,
                results,
                "RecommendationPerformanceEngine",
                lambda: RecommendationPerformanceEngine(db).build_summary(portfolio_id),
                lambda payload: 1,
            )

            _run_validation_step(
                db,
                results,
                "TradeAttributionEngine",
                lambda: TradeAttributionEngine(db).load_attribution_table(portfolio_id),
                lambda payload: len(payload),
            )

            _run_validation_step(
                db,
                results,
                "PortfolioRiskMonitor",
                lambda: PortfolioRiskMonitor(db).build_summary(portfolio_id),
                lambda payload: 1,
            )

            _run_validation_step(
                db,
                results,
                "RecommendationCommandCenter",
                lambda: RecommendationCommandCenter(db).self_test(portfolio_id=portfolio_id),
                lambda payload: 1,
            )

            _run_validation_step(
                db,
                results,
                "RecommendationAutopilotEngine",
                lambda: RecommendationAutopilotEngine(db).self_test(portfolio_id=portfolio_id),
                lambda payload: int(payload.get("actions", 0)) if isinstance(payload, dict) else 0,
            )

            _run_validation_step(
                db,
                results,
                "RecommendationLifecycleEngine",
                lambda: RecommendationLifecycleEngine(db).self_test(),
                lambda payload: int(payload.get("rows", 0)) if isinstance(payload, dict) else 0,
            )

            _run_validation_step(
                db,
                results,
                "RecommendationAlertCenter",
                lambda: RecommendationAlertCenter(db).self_test(portfolio_id=portfolio_id),
                lambda payload: int(payload.get("active_rows", 0)) if isinstance(payload, dict) else 0,
            )

            _run_validation_step(
                db,
                results,
                "RecommendationTargetTrackingEngine",
                lambda: RecommendationTargetTrackingEngine(db).self_test(),
                lambda payload: int(payload.get("rows", 0)) if isinstance(payload, dict) else 0,
            )

            _run_validation_step(
                db,
                results,
                "RecommendationStopLossMonitor",
                lambda: RecommendationStopLossMonitor(db).self_test(),
                lambda payload: int(payload.get("rows", 0)) if isinstance(payload, dict) else 0,
            )

            st.divider()
            st.subheader("Validation Summary")

            st.dataframe(
                results,
                use_container_width=True,
                hide_index=True,
            )

    with tabs[1]:
        _safe_render(
            "Recommendation Command Center",
            render_recommendation_command_center_dashboard,
            db=db,
            portfolio_id=portfolio_id,
        )

    with tabs[2]:
        _safe_render(
            "Recommendation Autopilot",
            render_recommendation_autopilot_dashboard,
            db=db,
            portfolio_id=portfolio_id,
        )

    with tabs[3]:
        _safe_render(
            "Recommendation Lifecycle Dashboard",
            render_recommendation_lifecycle_dashboard,
            db=db,
            portfolio_id=portfolio_id,
        )

    with tabs[4]:
        _safe_render(
            "Recommendation Alert Center",
            render_recommendation_alert_center_dashboard,
            db=db,
            portfolio_id=portfolio_id,
        )

    with tabs[5]:
        _safe_render(
            "Trade Management UI",
            render_trade_management_ui,
            db=db,
            portfolio_id=portfolio_id,
        )

    with tabs[6]:
        _safe_render(
            "Recommendation Performance UI",
            render_recommendation_performance_ui,
            db=db,
            portfolio_id=portfolio_id,
        )

    with tabs[7]:
        _safe_render(
            "Trade Attribution UI",
            render_trade_attribution_ui,
            db=db,
            portfolio_id=portfolio_id,
        )

    with tabs[8]:
        _safe_render(
            "Portfolio Risk Dashboard",
            render_portfolio_risk_dashboard,
            db=db,
            portfolio_id=portfolio_id,
        )

    _reset_failed_transaction(db)