"""
modules/forex/ui/forex_ui_layout.py

Sprint 22 — Phase 22.1
Institutional UI Foundation: layout helpers.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

from modules.forex.ui.forex_ui_theme import inject_forex_ui_theme


def _escape(value: Any) -> str:
    text = str(value if value is not None else "")
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def render_page_header(
    title: str,
    subtitle: str = "",
    *,
    icon: str = "🌐",
    meta: Optional[str] = None,
    st_module: Optional[Any] = None,
) -> None:
    if st_module is None:
        import streamlit as st_module  # type: ignore

    inject_forex_ui_theme(st_module)
    meta_text = meta or f"Live terminal • {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}"
    st_module.markdown(
        f"""
<div class="fx-page-header">
  <div class="fx-section-kicker">{_escape(meta_text)}</div>
  <h1 class="fx-page-title">{_escape(icon)} {_escape(title)}</h1>
  <div class="fx-page-subtitle">{_escape(subtitle)}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_section_header(
    title: str,
    *,
    kicker: str = "",
    meta: str = "",
    st_module: Optional[Any] = None,
) -> None:
    if st_module is None:
        import streamlit as st_module  # type: ignore

    left = f'<div><div class="fx-section-kicker">{_escape(kicker)}</div><h3 class="fx-section-title">{_escape(title)}</h3></div>'
    right = f'<div class="fx-section-meta">{_escape(meta)}</div>' if meta else ""
    st_module.markdown(
        f"""
<div class="fx-section-header">
  {left}
  {right}
</div>
""",
        unsafe_allow_html=True,
    )


def render_spacer(height: int = 10, st_module: Optional[Any] = None) -> None:
    if st_module is None:
        import streamlit as st_module  # type: ignore
    st_module.markdown(f'<div style="height:{int(height)}px"></div>', unsafe_allow_html=True)


@contextmanager
def panel(
    title: Optional[str] = None,
    *,
    kicker: str = "",
    meta: str = "",
    tight: bool = False,
    st_module: Optional[Any] = None,
):
    if st_module is None:
        import streamlit as st_module  # type: ignore

    cls = "fx-panel-tight" if tight else "fx-panel"
    st_module.markdown(f'<div class="{cls}">', unsafe_allow_html=True)
    if title:
        render_section_header(title, kicker=kicker, meta=meta, st_module=st_module)
    try:
        yield
    finally:
        st_module.markdown("</div>", unsafe_allow_html=True)


def render_workspace_shell(
    *,
    title: str,
    subtitle: str,
    icon: str = "🌐",
    left_title: str = "Analytics",
    center_title: str = "Workspace",
    right_title: str = "Intelligence",
    bottom_title: str = "Activity",
    st_module: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Create a common institutional layout shell.

    Returns a dict of Streamlit containers:
        {"left": left, "center": center, "right": right, "bottom": bottom}

    Example:
        shell = render_workspace_shell(...)
        with shell["center"]:
            st.write(...)
    """
    if st_module is None:
        import streamlit as st_module  # type: ignore

    render_page_header(title, subtitle, icon=icon, st_module=st_module)

    left, center, right = st_module.columns([1.05, 2.35, 1.25])
    bottom = st_module.container()

    with left:
        render_section_header(left_title, kicker="Left Panel", st_module=st_module)
    with center:
        render_section_header(center_title, kicker="Center Panel", st_module=st_module)
    with right:
        render_section_header(right_title, kicker="Right Panel", st_module=st_module)
    with bottom:
        render_section_header(bottom_title, kicker="Bottom Panel", st_module=st_module)

    return {"left": left, "center": center, "right": right, "bottom": bottom}


def render_two_column_shell(
    *,
    left_ratio: float = 1.0,
    right_ratio: float = 1.0,
    st_module: Optional[Any] = None,
):
    if st_module is None:
        import streamlit as st_module  # type: ignore
    return st_module.columns([left_ratio, right_ratio])


def render_ribbon_container(items: Iterable[str], st_module: Optional[Any] = None) -> None:
    if st_module is None:
        import streamlit as st_module  # type: ignore
    html = '<div class="fx-ribbon">' + "".join(items) + "</div>"
    st_module.markdown(html, unsafe_allow_html=True)
