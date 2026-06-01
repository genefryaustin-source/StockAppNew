"""
ui/admin/analytics_fabric_navigation.py
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import streamlit as st


PAGE_CONTROL_TOWER = "control_tower"
PAGE_OPERATIONS = "operations"
PAGE_VALIDATION = "validation"
PAGE_EXECUTIVE = "executive"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AnalyticsNavigationItem:
    page_id: str
    title: str
    icon: str
    description: str = ""
    enabled: bool = True
    sort_order: int = 0

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AnalyticsNavigationSection:
    section_id: str
    title: str
    items: List[AnalyticsNavigationItem] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "section_id": self.section_id,
            "title": self.title,
            "items": [item.as_dict() for item in self.items],
        }


@dataclass
class AnalyticsWorkspaceState:
    current_page: str
    last_page: Optional[str]
    page_history: List[Dict[str, Any]]
    generated_at: str = field(default_factory=utc_now_iso)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AnalyticsNavigationRegistry:
    def __init__(self) -> None:
        self._pages: Dict[str, AnalyticsNavigationItem] = {}
        self._renderers: Dict[str, Callable[..., None]] = {}

    def register_page(
        self,
        item: AnalyticsNavigationItem,
        renderer: Callable[..., None],
    ) -> None:
        self._pages[item.page_id] = item
        self._renderers[item.page_id] = renderer

    def get_page(
        self,
        page_id: str,
    ) -> Optional[AnalyticsNavigationItem]:
        return self._pages.get(page_id)

    def get_renderer(
        self,
        page_id: str,
    ) -> Optional[Callable[..., None]]:
        return self._renderers.get(page_id)

    def list_pages(self) -> List[AnalyticsNavigationItem]:
        return sorted(
            self._pages.values(),
            key=lambda x: x.sort_order,
        )

    def default_page(self) -> str:
        pages = self.list_pages()

        if not pages:
            return PAGE_CONTROL_TOWER

        return pages[0].page_id

    def export_state(self) -> Dict[str, Any]:
        return {
            "pages": [
                page.as_dict()
                for page in self.list_pages()
            ]
        }


def build_default_registry() -> AnalyticsNavigationRegistry:
    registry = AnalyticsNavigationRegistry()

    from ui.admin.analytics_fabric_control_tower import (
        render_analytics_fabric_control_tower,
    )

    from ui.admin.analytics_fabric_operations_center import (
        render_analytics_fabric_operations_center,
    )

    from ui.admin.analytics_fabric_validation_dashboard import (
        render_analytics_fabric_validation_dashboard,
    )

    from ui.admin.analytics_fabric_executive_dashboard import (
        render_analytics_fabric_executive_dashboard,
    )

    registry.register_page(
        AnalyticsNavigationItem(
            page_id=PAGE_CONTROL_TOWER,
            title="Control Tower",
            icon="🛰️",
            description="Global analytics command center.",
            sort_order=1,
        ),
        render_analytics_fabric_control_tower,
    )

    registry.register_page(
        AnalyticsNavigationItem(
            page_id=PAGE_OPERATIONS,
            title="Operations Center",
            icon="⚙️",
            description="Operational management and controls.",
            sort_order=2,
        ),
        render_analytics_fabric_operations_center,
    )

    registry.register_page(
        AnalyticsNavigationItem(
            page_id=PAGE_VALIDATION,
            title="Validation Center",
            icon="🧪",
            description="Validation, testing, and benchmarking.",
            sort_order=3,
        ),
        render_analytics_fabric_validation_dashboard,
    )

    registry.register_page(
        AnalyticsNavigationItem(
            page_id=PAGE_EXECUTIVE,
            title="Executive Dashboard",
            icon="📈",
            description="Executive KPIs and business metrics.",
            sort_order=4,
        ),
        render_analytics_fabric_executive_dashboard,
    )

    return registry


def initialize_workspace_state(
    registry: AnalyticsNavigationRegistry,
) -> None:
    default_page = registry.default_page()

    if "analytics_current_page" not in st.session_state:
        st.session_state["analytics_current_page"] = default_page

    if "analytics_last_page" not in st.session_state:
        st.session_state["analytics_last_page"] = None

    if "analytics_page_history" not in st.session_state:
        st.session_state["analytics_page_history"] = []


def navigate_to(page_id: str) -> None:
    current = st.session_state.get(
        "analytics_current_page"
    )

    if current == page_id:
        return

    st.session_state["analytics_last_page"] = current

    st.session_state["analytics_current_page"] = page_id

    history = st.session_state.setdefault(
        "analytics_page_history",
        [],
    )

    history.append(
        {
            "page_id": page_id,
            "timestamp": utc_now_iso(),
        }
    )

    if len(history) > 500:
        del history[:-500]


def get_workspace_state() -> AnalyticsWorkspaceState:
    return AnalyticsWorkspaceState(
        current_page=st.session_state.get(
            "analytics_current_page",
            PAGE_CONTROL_TOWER,
        ),
        last_page=st.session_state.get(
            "analytics_last_page"
        ),
        page_history=st.session_state.get(
            "analytics_page_history",
            [],
        ),
    )


def render_navigation_sidebar(
    registry: AnalyticsNavigationRegistry,
) -> None:
    st.sidebar.markdown("## ANALYTICS FABRIC")

    current_page = st.session_state.get(
        "analytics_current_page",
        registry.default_page(),
    )

    for page in registry.list_pages():
        selected = page.page_id == current_page

        label = (
            f"● {page.icon} {page.title}"
            if selected
            else f"○ {page.icon} {page.title}"
        )

        if st.sidebar.button(
            label,
            key=f"analytics_nav_{page.page_id}",
            use_container_width=True,
        ):
            navigate_to(page.page_id)

    st.sidebar.divider()

    workspace = get_workspace_state()

    st.sidebar.caption(
        f"Current: {workspace.current_page}"
    )

    if workspace.last_page:
        st.sidebar.caption(
            f"Previous: {workspace.last_page}"
        )


def render_current_page(
    registry: AnalyticsNavigationRegistry,
    storage: Optional[Any] = None,
    fabric: Optional[Any] = None,
) -> None:
    page_id = st.session_state.get(
        "analytics_current_page",
        registry.default_page(),
    )

    renderer = registry.get_renderer(page_id)

    if renderer is None:
        st.error(
            f"No renderer registered for page: {page_id}"
        )
        return

    renderer(
        storage=storage,
        fabric=fabric,
    )


def render_analytics_fabric_navigation(
    storage: Optional[Any] = None,
    fabric: Optional[Any] = None,
) -> None:
    registry = build_default_registry()

    initialize_workspace_state(registry)

    render_navigation_sidebar(registry)

    render_current_page(
        registry=registry,
        storage=storage,
        fabric=fabric,
    )


def render_analytics_workspace(
    storage: Optional[Any] = None,
    fabric: Optional[Any] = None,
) -> None:
    render_analytics_fabric_navigation(
        storage=storage,
        fabric=fabric,
    )


def export_navigation_state() -> Dict[str, Any]:
    registry = build_default_registry()

    return {
        "workspace": get_workspace_state().as_dict(),
        "registry": registry.export_state(),
        "generated_at": utc_now_iso(),
    }


if __name__ == "__main__":
    st.set_page_config(
        page_title="Analytics Fabric Workspace",
        layout="wide",
    )

    render_analytics_fabric_navigation()