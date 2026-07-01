"""
modules/forex/ui/forex_ui_cards.py

Sprint 22 — Phase 22.2
KPI & Card Framework.

Reusable institutional metric cards for every Forex workspace.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Optional

from modules.forex.ui.forex_ui_theme import inject_forex_ui_theme
from modules.forex.ui.forex_ui_status import status_color, normalize_status


def _escape(value: Any) -> str:
    text = str(value if value is not None else "")
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str):
            value = value.replace("$", "").replace(",", "").replace("%", "").strip()
            if value in {"", "-", "—"}:
                return default
        return float(value)
    except Exception:
        return default


@dataclass
class ForexMetricCard:
    label: str
    value: Any
    caption: str = ""
    delta: Any = None
    color: Optional[str] = None
    progress: Optional[float] = None
    status: Optional[str] = None
    icon: str = ""
    mono: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _value_color(card: ForexMetricCard) -> str:
    if card.color:
        return card.color
    if card.status:
        return status_color(card.status)
    value = _safe_float(card.delta, None)
    if value is not None:
        if value > 0:
            return "var(--fx-green)"
        if value < 0:
            return "var(--fx-red)"
    return "var(--fx-text)"


def _progress_width(progress: Optional[float]) -> float:
    if progress is None:
        return 0.0
    try:
        val = float(progress)
        if val <= 1:
            val *= 100
        return max(0.0, min(100.0, val))
    except Exception:
        return 0.0


def metric_card_html(card: ForexMetricCard | Dict[str, Any]) -> str:
    if isinstance(card, dict):
        card = ForexMetricCard(**card)

    value_class = "fx-card-value fx-mono" if card.mono else "fx-card-value"
    color = _value_color(card)
    icon = f"{_escape(card.icon)} " if card.icon else ""
    delta_html = ""
    if card.delta not in (None, ""):
        delta_val = _safe_float(card.delta, 0)
        arrow = "▲" if delta_val > 0 else "▼" if delta_val < 0 else "■"
        delta_color = "var(--fx-green)" if delta_val > 0 else "var(--fx-red)" if delta_val < 0 else "var(--fx-muted)"
        delta_html = f'<span style="color:{delta_color}; font-weight:800; margin-left:6px;">{arrow} {_escape(card.delta)}</span>'

    progress_html = ""
    if card.progress is not None:
        width = _progress_width(card.progress)
        progress_html = f'<div class="fx-progress"><span style="width:{width:.1f}%"></span></div>'

    status_html = ""
    if card.status:
        pill_color = status_color(card.status)
        status_html = (
            f'<div style="margin-top:7px;">'
            f'<span class="fx-pill">'
            f'<span class="fx-pill-dot" style="background:{pill_color}; box-shadow:0 0 10px {pill_color};"></span>'
            f'{_escape(normalize_status(card.status).replace("_", " ").title())}'
            f'</span></div>'
        )

    return f"""
<div class="fx-card">
  <div class="fx-card-label">{icon}{_escape(card.label)}</div>
  <div class="{value_class}" style="color:{color};">{_escape(card.value)}{delta_html}</div>
  <div class="fx-card-caption">{_escape(card.caption)}</div>
  {progress_html}
  {status_html}
</div>
"""


def render_metric_card(card: ForexMetricCard | Dict[str, Any], *, st_module: Optional[Any] = None) -> None:
    if st_module is None:
        import streamlit as st_module  # type: ignore

    inject_forex_ui_theme(st_module)
    st_module.markdown(metric_card_html(card), unsafe_allow_html=True)


def render_metric_ribbon(
    cards: Iterable[ForexMetricCard | Dict[str, Any]],
    *,
    st_module: Optional[Any] = None,
) -> None:
    if st_module is None:
        import streamlit as st_module  # type: ignore

    inject_forex_ui_theme(st_module)
    html = '<div class="fx-ribbon">' + "".join(metric_card_html(card) for card in cards) + "</div>"
    st_module.markdown(html, unsafe_allow_html=True)


def render_status_metric_card(
    *,
    label: str,
    status: str,
    caption: str = "",
    icon: str = "",
    progress: Optional[float] = None,
    st_module: Optional[Any] = None,
) -> None:
    render_metric_card(
        ForexMetricCard(
            label=label,
            value=normalize_status(status).replace("_", " ").title(),
            caption=caption,
            status=status,
            icon=icon,
            progress=progress,
        ),
        st_module=st_module,
    )


def cards_from_dict(payload: Dict[str, Any], mapping: Dict[str, str]) -> List[ForexMetricCard]:
    """
    Convert a dictionary into cards.

    mapping example:
        {"equity": "Equity", "daily_pnl": "Daily P/L"}
    """
    cards = []
    for key, label in mapping.items():
        cards.append(ForexMetricCard(label=label, value=payload.get(key, "-")))
    return cards
