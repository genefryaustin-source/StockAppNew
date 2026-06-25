# modules/forex/forex_workstation.py

from __future__ import annotations

import streamlit as st

from typing import Any, Optional

try:
    from modules.forex.forex_dashboard import render_forex_dashboard
except Exception:
    render_forex_dashboard = None

try:
    from modules.forex.forex_command_center import (
        render_forex_command_center,
    )
except Exception:
    render_forex_command_center = None

try:
    from modules.forex.forex_recommendation_dashboard import (
        render_forex_recommendation_dashboard,
    )
except Exception:
    render_forex_recommendation_dashboard = None

try:
    from modules.forex.forex_macro_dashboard import (
        render_forex_macro_dashboard,
    )
except Exception:
    render_forex_macro_dashboard = None

try:
    from modules.forex.forex_liquidity_dashboard import (
        render_forex_liquidity_dashboard,
    )
except Exception:
    render_forex_liquidity_dashboard = None

try:
    from modules.forex.forex_execution_quality_dashboard import (
        render_forex_execution_quality_dashboard,
    )
except Exception:
    render_forex_execution_quality_dashboard = None

try:
    from modules.forex.forex_attribution_dashboard import (
        render_forex_attribution_dashboard,
    )
except Exception:
    render_forex_attribution_dashboard = None

try:
    from modules.forex.forex_validation_dashboard import (
        render_forex_validation_dashboard,
    )
except Exception:
    render_forex_validation_dashboard = None

try:
    from modules.forex.forex_risk_dashboard import (
        render_forex_risk_dashboard,
    )
except Exception:
    render_forex_risk_dashboard = None

try:
    from modules.forex.forex_execution_dashboard import (
        render_forex_execution_dashboard,
    )
except Exception:
        render_forex_execution_dashboard = None

try:
    from modules.forex.forex_order_flow_dashboard import (
        render_forex_order_flow_dashboard,
    )
except Exception:
    render_forex_order_flow_dashboard = None


# ============================================================
# Helpers
# ============================================================

def _safe_render(
    renderer,
    **kwargs,
) -> None:
    if renderer is None:
        st.warning(
            "Module not installed or dashboard unavailable."
        )
        return

    try:
        renderer(**kwargs)
    except Exception as exc:
        st.error(
            f"Dashboard failed to load: {exc}"
        )


# ============================================================
# Main Workstation
# ============================================================

def render_forex_workstation(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
) -> None:

    st.title("Forex Institutional Workstation")

    st.caption(
        "Trading • Macro • Liquidity • Order Flow • Risk • Execution • Validation"
    )

    workspace = st.radio(
        "Forex Workspace",
        [
            "Command Center",
            "Market Intelligence",
            "Trading",
            "Execution",
            "Institutional",
            "Validation",
        ],
        horizontal=True,
        key="forex_workstation_workspace",
    )

    if workspace == "Command Center":
        render_command_center(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )

    elif workspace == "Market Intelligence":
        render_market_intelligence(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )

    elif workspace == "Trading":
        render_trading_workspace(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )

    elif workspace == "Execution":
        render_execution_workspace(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )

    elif workspace == "Institutional":
        render_institutional_workspace(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )

    elif workspace == "Validation":
        render_validation_workspace(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )


# ============================================================
# Command Center
# ============================================================

def render_command_center(
    *,
    tenant_id: Optional[str],
    user_id: Optional[str],
    portfolio_id: Optional[str],
    db: Any,
) -> None:

    _safe_render(
        render_forex_command_center,
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )


# ============================================================
# Market Intelligence
# ============================================================

def render_market_intelligence(
    *,
    tenant_id: Optional[str],
    user_id: Optional[str],
    portfolio_id: Optional[str],
    db: Any,
) -> None:

    intelligence_workspace = st.radio(
        "Market Intelligence Workspace",
        [
            "Overview",
            "Recommendations",
            "Macro",
            "Liquidity",
        ],
        horizontal=True,
        key="forex_market_intelligence_workspace",
    )

    if intelligence_workspace == "Overview":
        _safe_render(
            render_forex_dashboard,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )

    elif intelligence_workspace == "Recommendations":
        _safe_render(
            render_forex_recommendation_dashboard,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )

    elif intelligence_workspace == "Macro":
        _safe_render(
            render_forex_macro_dashboard,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )

    elif intelligence_workspace == "Liquidity":
        _safe_render(
            render_forex_liquidity_dashboard,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )


# ============================================================
# Trading
# ============================================================

def render_trading_workspace(
    *,
    tenant_id: Optional[str],
    user_id: Optional[str],
    portfolio_id: Optional[str],
    db: Any,
) -> None:

    trading_workspace = st.radio(
        "Trading Workspace",
        [
            "Recommendations",
            "Execution Quality",
            "Attribution",
        ],
        horizontal=True,
        key="forex_trading_workspace",
    )

    if trading_workspace == "Recommendations":
        _safe_render(
            render_forex_recommendation_dashboard,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )

    elif trading_workspace == "Execution Quality":
        _safe_render(
            render_forex_execution_quality_dashboard,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )

    elif trading_workspace == "Attribution":
        _safe_render(
            render_forex_attribution_dashboard,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )


# ============================================================
# Execution
# ============================================================

def render_execution_workspace(
    *,
    tenant_id: Optional[str],
    user_id: Optional[str],
    portfolio_id: Optional[str],
    db: Any,
) -> None:

    execution_workspace = st.radio(
        "Execution Workspace",
        [
            "Execution Center",
            "Execution Quality",
            "Order Flow",
        ],
        horizontal=True,
        key="forex_execution_workspace",
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

    elif execution_workspace == "Order Flow":
        _safe_render(
            render_forex_order_flow_dashboard,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )


# ============================================================
# Institutional
# ============================================================

def render_institutional_workspace(
    *,
    tenant_id: Optional[str],
    user_id: Optional[str],
    portfolio_id: Optional[str],
    db: Any,
) -> None:

    institutional_workspace = st.radio(
        "Institutional Workspace",
        [
            "Macro",
            "Liquidity",
            "Order Flow",
            "Execution Quality",
        ],
        horizontal=True,
        key="forex_institutional_workspace",
    )

    if institutional_workspace == "Macro":
        _safe_render(
            render_forex_macro_dashboard,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )

    elif institutional_workspace == "Liquidity":
        _safe_render(
            render_forex_liquidity_dashboard,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )

    elif institutional_workspace == "Order Flow":
        _safe_render(
            render_forex_order_flow_dashboard,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )

    elif institutional_workspace == "Execution Quality":
        _safe_render(
            render_forex_execution_quality_dashboard,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )


# ============================================================
# Validation
# ============================================================

def render_validation_workspace(
    *,
    tenant_id: Optional[str],
    user_id: Optional[str],
    portfolio_id: Optional[str],
    db: Any,
) -> None:

    _safe_render(
        render_forex_validation_dashboard,
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
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
    render_forex_workstation(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )