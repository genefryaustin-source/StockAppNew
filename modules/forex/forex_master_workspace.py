# modules/forex/forex_master_workspace.py

from __future__ import annotations

try:
    import streamlit as st
except Exception:
    st = None


def _safe_render(
    import_path: str,
    function_name: str,
    fallback_label: str,
    db=None,
    user=None,
    tenant_id=None,
    portfolio_id=None,
):
    try:
        module = __import__(import_path, fromlist=[function_name])
        fn = getattr(module, function_name)

        try:
            return fn(
                db=db,
                user=user,
                tenant_id=tenant_id,
                portfolio_id=portfolio_id,
            )
        except TypeError:
            try:
                return fn(db=db, user=user)
            except TypeError:
                return fn()

    except Exception as exc:
        if st is not None:
            st.warning(f"{fallback_label} is not available yet: {exc}")
            st.exception(exc)

        return {
            "status": "unavailable",
            "module": import_path,
            "function": function_name,
            "error": str(exc),
        }


def _render_research_workspace(db=None, user=None, tenant_id=None, portfolio_id=None):
    research = st.radio(
        "Research Workspace",
        [
            "Currency Strength",
            "Regime Detection",
            "Macro Regime",
            "Sentiment",
            "Central Banks",
            "Intermarket",
            "Carry Trades",
        ],
        horizontal=True,
        key="forex_research_workspace_radio",
    )

    routes = {
        "Currency Strength": (
            "modules.forex.forex_currency_strength_dashboard",
            "render_forex_currency_strength_dashboard",
        ),
        "Regime Detection": (
            "modules.forex.forex_regime_detection_dashboard",
            "render_forex_regime_detection_dashboard",
        ),
        "Macro Regime": (
            "modules.forex.forex_macro_regime_dashboard",
            "render_forex_macro_regime_dashboard",
        ),
        "Sentiment": (
            "modules.forex.forex_sentiment_dashboard",
            "render_forex_sentiment_dashboard",
        ),
        "Central Banks": (
            "modules.forex.forex_central_bank_dashboard",
            "render_forex_central_bank_dashboard",
        ),
        "Intermarket": (
            "modules.forex.forex_intermarket_dashboard",
            "render_forex_intermarket_dashboard",
        ),
        "Carry Trades": (
            "modules.forex.forex_carry_trade_dashboard",
            "render_forex_carry_trade_dashboard",
        ),
    }

    module, function = routes[research]
    return _safe_render(module, function, research, db, user, tenant_id, portfolio_id)


def _render_trading_workspace(db=None, user=None, tenant_id=None, portfolio_id=None):
    trading = st.radio(
        "Trading Workspace",
        [
            "AI Recommendations",
            "Alpha Model",
            "Strategy Lab",
            "Autonomous Trader",
            "Execution",
            "Risk",
        ],
        horizontal=True,
        key="forex_trading_workspace_radio",
    )

    routes = {
        "AI Recommendations": (
            "modules.forex.forex_recommendation_dashboard",
            "render_forex_recommendation_dashboard",
        ),
        "Alpha Model": (
            "modules.forex.forex_alpha_model_dashboard",
            "render_forex_alpha_model_dashboard",
        ),
        "Strategy Lab": (
            "modules.forex.forex_strategy_lab",
            "render_forex_strategy_lab",
        ),
        "Autonomous Trader": (
            "modules.forex.forex_autonomous_trader",
            "render_forex_autonomous_trader",
        ),
        "Execution": (
            "modules.forex.forex_execution_dashboard",
            "render_forex_execution_dashboard",
        ),
        "Risk": (
            "modules.forex.forex_risk_dashboard",
            "render_forex_risk_dashboard",
        ),
    }

    module, function = routes[trading]
    return _safe_render(module, function, trading, db, user, tenant_id, portfolio_id)


def _render_intelligence_workspace(db=None, user=None, tenant_id=None, portfolio_id=None):
    intelligence = st.radio(
        "Intelligence Workspace",
        [
            "Institutional Scanner",
            "Smart Money",
            "Order Flow",
            "Dealer Positioning",
            "Liquidity",
            "Market Structure",
            "Flow of Funds",
        ],
        horizontal=True,
        key="forex_intelligence_workspace_radio",
    )

    routes = {
        "Institutional Scanner": (
            "modules.forex.forex_institutional_command_center",
            "render_forex_institutional_command_center",
        ),
        "Smart Money": (
            "modules.forex.forex_smart_money_dashboard",
            "render_forex_smart_money_dashboard",
        ),
        "Order Flow": (
            "modules.forex.forex_order_flow_dashboard",
            "render_forex_order_flow_dashboard",
        ),
        "Dealer Positioning": (
            "modules.forex.forex_dealer_positioning_dashboard",
            "render_forex_dealer_positioning_dashboard",
        ),
        "Liquidity": (
            "modules.forex.forex_liquidity_dashboard",
            "render_forex_liquidity_dashboard",
        ),
        "Market Structure": (
            "modules.forex.forex_market_structure_dashboard",
            "render_forex_market_structure_dashboard",
        ),
        "Flow of Funds": (
            "modules.forex.forex_flow_of_funds_dashboard",
            "render_forex_flow_of_funds_dashboard",
        ),
    }

    module, function = routes[intelligence]
    return _safe_render(module, function, intelligence, db, user, tenant_id, portfolio_id)


def _render_portfolio_workspace(db=None, user=None, tenant_id=None, portfolio_id=None):
    portfolio = st.radio(
        "Portfolio Workspace",
        [
            "Portfolio Optimizer",
            "Attribution",
            "Correlation",
            "Execution Quality",
        ],
        horizontal=True,
        key="forex_portfolio_workspace_radio",
    )

    routes = {
        "Portfolio Optimizer": (
            "modules.forex.forex_portfolio_optimizer_dashboard",
            "render_forex_portfolio_optimizer_dashboard",
        ),
        "Attribution": (
            "modules.forex.forex_attribution_dashboard",
            "render_forex_attribution_dashboard",
        ),
        "Correlation": (
            "modules.forex.forex_correlation_dashboard",
            "render_forex_correlation_dashboard",
        ),
        "Execution Quality": (
            "modules.forex.forex_execution_quality_dashboard",
            "render_forex_execution_quality_dashboard",
        ),
    }

    module, function = routes[portfolio]
    return _safe_render(module, function, portfolio, db, user, tenant_id, portfolio_id)


def _render_operations_workspace(db=None, user=None, tenant_id=None, portfolio_id=None):
    operations = st.radio(
        "Operations Workspace",
        [
            "Operations Dashboard",
            "Runtime Dashboard",
            "Scheduler Dashboard",
            "Optimizer Dashboard",
            "Governor Dashboard",
            "Operations Command Center",
            "Control Center",
        ],
        horizontal=True,
        key="forex_operations_workspace_radio",
    )

    routes = {
        "Operations Dashboard": (
            "modules.forex.forex_operations_dashboard",
            "render_forex_operations_dashboard",
        ),
        "Runtime Dashboard": (
            "modules.forex.forex_runtime_dashboard",
            "render_forex_runtime_dashboard",
        ),
        "Scheduler Dashboard": (
            "modules.forex.forex_scheduler_dashboard",
            "render_forex_scheduler_dashboard",
        ),
        "Optimizer Dashboard": (
            "modules.forex.forex_optimizer_dashboard",
            "render_forex_optimizer_dashboard",
        ),
        "Governor Dashboard": (
            "modules.forex.forex_governor_dashboard",
            "render_forex_governor_dashboard",
        ),
        "Operations Command Center": (
            "modules.forex.forex_command_center",
            "render_forex_command_center",
        ),
        "Control Center": (
            "modules.forex.forex_control_center",
            "render_forex_control_center",
        ),
    }

    module, function = routes[operations]
    return _safe_render(module, function, operations, db, user, tenant_id, portfolio_id)


def _render_validation_workspace(db=None, user=None, tenant_id=None, portfolio_id=None):
    validation = st.radio(
        "Validation Workspace",
        [
            "Validation Dashboard",
            "Validation Center",
            "Validation Operations",
            "Validation Runtime",
            "Validation Scheduler",
            "Release Dashboard",
            "Management Console",
        ],
        horizontal=True,
        key="forex_validation_workspace_radio",
    )

    routes = {
        "Validation Dashboard": (
            "modules.forex.forex_validation_dashboard",
            "render_forex_validation_dashboard",
        ),
        "Validation Center": (
            "modules.forex.forex_admin_validation_center",
            "render_forex_admin_validation_center",
        ),
        "Validation Operations": (
            "modules.forex.forex_validation_operations_dashboard",
            "render_forex_validation_operations_dashboard",
        ),
        "Validation Runtime": (
            "modules.forex.forex_validation_runtime_dashboard",
            "render_forex_validation_runtime_dashboard",
        ),
        "Validation Scheduler": (
            "modules.forex.forex_validation_scheduler_dashboard",
            "render_forex_validation_scheduler_dashboard",
        ),
        "Release Dashboard": (
            "modules.forex.forex_release_dashboard",
            "render_forex_release_dashboard",
        ),
        "Management Console": (
            "modules.forex.forex_validation_management_console",
            "render_forex_validation_management_console",
        ),
    }

    module, function = routes[validation]
    return _safe_render(module, function, validation, db, user, tenant_id, portfolio_id)


def render_forex_master_workspace(
    db=None,
    user=None,
    tenant_id=None,
    portfolio_id=None,
):
    if st is None:
        return {"status": "streamlit_unavailable"}

    st.title("Forex Master Workspace")
    st.caption(
        "Trader-facing Forex command center with research, trading, intelligence, portfolio, operations, and validation workspaces."
    )

    workspace = st.radio(
        "Workspace",
        [
            "Command Center",
            "Research",
            "Trading",
            "Intelligence",
            "Portfolio",
            "Operations",
            "Validation",
        ],
        horizontal=True,
        key="forex_master_workspace_radio",
    )

    if workspace == "Command Center":
        return _safe_render(
            "modules.forex.forex_trader_command_center",
            "render_forex_trader_command_center",
            workspace,
            db,
            user,
            tenant_id,
            portfolio_id,
        )

    if workspace == "Research":
        return _render_research_workspace(db, user, tenant_id, portfolio_id)

    if workspace == "Trading":
        return _render_trading_workspace(db, user, tenant_id, portfolio_id)

    if workspace == "Intelligence":
        return _render_intelligence_workspace(db, user, tenant_id, portfolio_id)

    if workspace == "Portfolio":
        return _render_portfolio_workspace(db, user, tenant_id, portfolio_id)

    if workspace == "Operations":
        return _render_operations_workspace(db, user, tenant_id, portfolio_id)

    return _render_validation_workspace(db, user, tenant_id, portfolio_id)
