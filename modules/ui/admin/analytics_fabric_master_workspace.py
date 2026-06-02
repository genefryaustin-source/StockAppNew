"""
ui/admin/analytics_fabric_master_workspace.py
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Optional

import streamlit as st


PAGE_CONTROL_PLANE = "control_plane"
PAGE_COMMAND_CENTER = "command_center"
PAGE_CONTINUOUS_RUNTIME = "continuous_runtime"
PAGE_AUTONOMOUS_SUPERVISOR = "autonomous_supervisor"
PAGE_RUNTIME_CONTROL = "runtime_control"
PAGE_EXECUTION_ORCHESTRATOR = "execution_orchestrator"
PAGE_EXECUTION_PLANNER = "execution_planner"
PAGE_FORECAST_OPTIMIZER = "forecast_optimizer"
PAGE_FORECASTING = "forecasting"
PAGE_HISTORY_CONTROL = "history_control"
PAGE_HISTORY = "history"
PAGE_CONTROL_TOWER = "control_tower"
PAGE_EXECUTIVE = "executive"
PAGE_VALIDATION = "validation"
PAGE_OPERATIONS = "operations"


MASTER_ANALYTICS_PAGES = {
    PAGE_CONTROL_PLANE: {
        "title": "Control Plane",
        "icon": "🧠",
        "description": "Top-level Analytics Fabric platform control.",
        "group": "Platform",
    },
    PAGE_COMMAND_CENTER: {
        "title": "Command Center",
        "icon": "⌨️",
        "description": "Command processor and approval console.",
        "group": "Platform",
    },
    PAGE_CONTINUOUS_RUNTIME: {
        "title": "Continuous Runtime",
        "icon": "♾️",
        "description": "Always-on runtime loop control.",
        "group": "Runtime",
    },
    PAGE_AUTONOMOUS_SUPERVISOR: {
        "title": "Autonomous Supervisor",
        "icon": "🛰️",
        "description": "Autonomous cycle supervision.",
        "group": "Runtime",
    },
    PAGE_RUNTIME_CONTROL: {
        "title": "Runtime Control",
        "icon": "🎛️",
        "description": "Runtime controller command room.",
        "group": "Runtime",
    },
    PAGE_EXECUTION_ORCHESTRATOR: {
        "title": "Execution Orchestrator",
        "icon": "🚦",
        "description": "Execution lifecycle orchestration.",
        "group": "Execution",
    },
    PAGE_EXECUTION_PLANNER: {
        "title": "Execution Planner",
        "icon": "🧭",
        "description": "Executable action planning.",
        "group": "Execution",
    },
    PAGE_FORECAST_OPTIMIZER: {
        "title": "Forecast Optimizer",
        "icon": "⚡",
        "description": "Closed-loop forecast optimization.",
        "group": "Predictive",
    },
    PAGE_FORECASTING: {
        "title": "Forecasting",
        "icon": "📈",
        "description": "Predictive analytics forecasts.",
        "group": "Predictive",
    },
    PAGE_HISTORY_CONTROL: {
        "title": "History Control",
        "icon": "🗄️",
        "description": "Snapshot and history operations.",
        "group": "History",
    },
    PAGE_HISTORY: {
        "title": "History Dashboard",
        "icon": "📚",
        "description": "Historical intelligence dashboard.",
        "group": "History",
    },
    PAGE_CONTROL_TOWER: {
        "title": "Control Tower",
        "icon": "🏢",
        "description": "Analytics Fabric single-pane command center.",
        "group": "Executive",
    },
    PAGE_EXECUTIVE: {
        "title": "Executive Dashboard",
        "icon": "📊",
        "description": "Executive KPIs and business view.",
        "group": "Executive",
    },
    PAGE_VALIDATION: {
        "title": "Validation Center",
        "icon": "🧪",
        "description": "Validation, benchmarks, and stress testing.",
        "group": "Testing",
    },
    PAGE_OPERATIONS: {
        "title": "Operations Center",
        "icon": "⚙️",
        "description": "Analytics operations management.",
        "group": "Operations",
    },
}


def _safe_render(render_fn, **kwargs):
    try:
        render_fn(**kwargs)
    except TypeError:
        try:
            render_fn(kwargs.get("analytics_fabric"))
        except TypeError:
            render_fn()
    except Exception as exc:
        st.error(f"Unable to render dashboard: {exc}")


def _page_key() -> str:
    return "analytics_fabric_master_workspace_page"


def _init_state() -> None:
    if _page_key() not in st.session_state:
        st.session_state[_page_key()] = PAGE_CONTROL_PLANE

    if "analytics_fabric_master_workspace_history" not in st.session_state:
        st.session_state["analytics_fabric_master_workspace_history"] = []


def _navigate(page_id: str) -> None:
    previous = st.session_state.get(_page_key())

    if previous != page_id:
        st.session_state["analytics_fabric_master_workspace_history"].append(
            {
                "from": previous,
                "to": page_id,
            }
        )

    st.session_state[_page_key()] = page_id


def _render_sidebar() -> None:
    st.sidebar.markdown("## Analytics Fabric")

    groups = {}

    for page_id, page in MASTER_ANALYTICS_PAGES.items():
        groups.setdefault(page["group"], []).append((page_id, page))

    for group_name, items in groups.items():
        st.sidebar.markdown(f"### {group_name}")

        for page_id, page in items:
            selected = st.session_state.get(_page_key()) == page_id
            prefix = "●" if selected else "○"

            if st.sidebar.button(
                f"{prefix} {page['icon']} {page['title']}",
                key=f"analytics_master_nav_{page_id}",
                use_container_width=True,
            ):
                _navigate(page_id)
                st.rerun()

    st.sidebar.divider()

    current_page = MASTER_ANALYTICS_PAGES.get(
        st.session_state.get(_page_key()),
        {},
    )

    st.sidebar.caption(
        f"Current: {current_page.get('title', 'Unknown')}"
    )


def _render_header() -> None:
    page_id = st.session_state.get(_page_key())
    page = MASTER_ANALYTICS_PAGES.get(page_id, {})

    st.title("Analytics Fabric Master Workspace")

    st.caption(
        f"{page.get('icon', '')} {page.get('title', '')} — "
        f"{page.get('description', '')}"
    )


def _render_page(
    page_id: str,
    analytics_fabric: Optional[Any] = None,
) -> None:
    if page_id == PAGE_CONTROL_PLANE:
        from ui.admin.analytics_fabric_control_plane_dashboard import (
            render_analytics_fabric_control_plane_dashboard,
        )

        _safe_render(
            render_analytics_fabric_control_plane_dashboard,
            analytics_fabric=analytics_fabric,
        )
        return

    if page_id == PAGE_COMMAND_CENTER:
        from ui.admin.analytics_fabric_command_center import (
            render_analytics_fabric_command_center,
        )

        _safe_render(
            render_analytics_fabric_command_center,
            analytics_fabric=analytics_fabric,
        )
        return

    if page_id == PAGE_CONTINUOUS_RUNTIME:
        from ui.admin.analytics_fabric_continuous_runtime_dashboard import (
            render_analytics_fabric_continuous_runtime_dashboard,
        )

        _safe_render(
            render_analytics_fabric_continuous_runtime_dashboard,
            analytics_fabric=analytics_fabric,
        )
        return

    if page_id == PAGE_AUTONOMOUS_SUPERVISOR:
        from ui.admin.analytics_fabric_autonomous_supervisor_dashboard import (
            render_analytics_fabric_autonomous_supervisor_dashboard,
        )

        _safe_render(
            render_analytics_fabric_autonomous_supervisor_dashboard,
            analytics_fabric=analytics_fabric,
        )
        return

    if page_id == PAGE_RUNTIME_CONTROL:
        from ui.admin.analytics_fabric_runtime_control_center import (
            render_analytics_fabric_runtime_control_center,
        )

        _safe_render(
            render_analytics_fabric_runtime_control_center,
            analytics_fabric=analytics_fabric,
        )
        return

    if page_id == PAGE_EXECUTION_ORCHESTRATOR:
        from ui.admin.autonomous_execution_orchestrator_dashboard import (
            render_autonomous_execution_orchestrator_dashboard,
        )

        _safe_render(
            render_autonomous_execution_orchestrator_dashboard,
            analytics_fabric=analytics_fabric,
        )
        return

    if page_id == PAGE_EXECUTION_PLANNER:
        from ui.admin.autonomous_execution_planner_dashboard import (
            render_autonomous_execution_planner_dashboard,
        )

        _safe_render(
            render_autonomous_execution_planner_dashboard,
            analytics_fabric=analytics_fabric,
        )
        return

    if page_id == PAGE_FORECAST_OPTIMIZER:
        from ui.admin.autonomous_forecast_optimizer_dashboard import (
            render_autonomous_forecast_optimizer_dashboard,
        )

        _safe_render(
            render_autonomous_forecast_optimizer_dashboard,
        )
        return

    if page_id == PAGE_FORECASTING:
        from ui.admin.analytics_fabric_forecasting_dashboard import (
            render_analytics_fabric_forecasting_dashboard,
        )

        _safe_render(
            render_analytics_fabric_forecasting_dashboard,
        )
        return

    if page_id == PAGE_HISTORY_CONTROL:
        from ui.admin.analytics_fabric_history_control_center import (
            render_analytics_fabric_history_control_center,
        )

        _safe_render(
            render_analytics_fabric_history_control_center,
            analytics_fabric=analytics_fabric,
        )
        return

    if page_id == PAGE_HISTORY:
        from ui.admin.analytics_fabric_history_dashboard import (
            render_analytics_fabric_history_dashboard,
        )

        _safe_render(
            render_analytics_fabric_history_dashboard,
        )
        return

    if page_id == PAGE_CONTROL_TOWER:
        from ui.admin.analytics_fabric_control_tower import (
            render_analytics_fabric_control_tower,
        )

        _safe_render(
            render_analytics_fabric_control_tower,
            fabric=analytics_fabric,
        )
        return

    if page_id == PAGE_EXECUTIVE:
        from ui.admin.analytics_fabric_executive_dashboard import (
            render_analytics_fabric_executive_dashboard,
        )

        _safe_render(
            render_analytics_fabric_executive_dashboard,
            fabric=analytics_fabric,
        )
        return

    if page_id == PAGE_VALIDATION:
        from ui.admin.analytics_fabric_validation_dashboard import (
            render_analytics_fabric_validation_dashboard,
        )

        _safe_render(
            render_analytics_fabric_validation_dashboard,
            fabric=analytics_fabric,
        )
        return

    if page_id == PAGE_OPERATIONS:
        from ui.admin.analytics_fabric_operations_center import (
            render_analytics_fabric_operations_center,
        )

        _safe_render(
            render_analytics_fabric_operations_center,
            fabric=analytics_fabric,
        )
        return

    st.error(f"Unknown Analytics Fabric page: {page_id}")


def render_analytics_fabric_master_workspace(
    analytics_fabric: Optional[Any] = None,
) -> None:
    _init_state()
    _render_sidebar()
    _render_header()

    page_id = st.session_state.get(
        _page_key(),
        PAGE_CONTROL_PLANE,
    )

    _render_page(
        page_id,
        analytics_fabric=analytics_fabric,
    )


def render_analytics_master_workspace(
    analytics_fabric: Optional[Any] = None,
) -> None:
    render_analytics_fabric_master_workspace(
        analytics_fabric=analytics_fabric,
    )


if __name__ == "__main__":
    st.set_page_config(
        page_title="Analytics Fabric Master Workspace",
        layout="wide",
    )

    render_analytics_fabric_master_workspace()