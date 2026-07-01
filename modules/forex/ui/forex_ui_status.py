"""
modules/forex/ui/forex_ui_status.py

Sprint 22 — Phase 22.1
Institutional UI Foundation: status helpers.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


STATUS_COLORS = {
    "READY": "#2ff58d",
    "HEALTHY": "#2ff58d",
    "ONLINE": "#2ff58d",
    "PASS": "#2ff58d",
    "FILLED": "#2ff58d",
    "OPEN": "#20d6ff",
    "ACTIVE": "#20d6ff",
    "RUNNING": "#20d6ff",
    "WATCH": "#ffd166",
    "WARNING": "#ffd166",
    "DEGRADED": "#ffd166",
    "HOLD": "#ffd166",
    "REVIEW": "#ffd166",
    "REJECTED": "#ff4d6d",
    "FAIL": "#ff4d6d",
    "ERROR": "#ff4d6d",
    "OFFLINE": "#ff4d6d",
    "DISABLED": "#6f8aa0",
    "UNKNOWN": "#9bb5c9",
}


def normalize_status(status: Any) -> str:
    value = str(status or "UNKNOWN").strip().upper()
    if value in {"OK", "SUCCESS", "SUCCEEDED"}:
        return "READY"
    if value in {"WARN"}:
        return "WARNING"
    if value in {"FAILED", "FAILURE"}:
        return "FAIL"
    return value or "UNKNOWN"


def status_color(status: Any) -> str:
    return STATUS_COLORS.get(normalize_status(status), STATUS_COLORS["UNKNOWN"])


def status_label(status: Any) -> str:
    return normalize_status(status).replace("_", " ").title()


def render_status_pill(
    status: Any,
    *,
    label: Optional[str] = None,
    st_module: Optional[Any] = None,
) -> None:
    if st_module is None:
        import streamlit as st_module  # type: ignore

    norm = normalize_status(status)
    color = status_color(norm)
    text = label or status_label(norm)
    st_module.markdown(
        f"""
<span class="fx-pill">
  <span class="fx-pill-dot" style="background:{color}; box-shadow:0 0 10px {color};"></span>
  {text}
</span>
""",
        unsafe_allow_html=True,
    )


def render_health_pill(
    payload: Dict[str, Any] | None,
    *,
    label: str = "Health",
    st_module: Optional[Any] = None,
) -> None:
    payload = payload or {}
    status = payload.get("status") or payload.get("health") or payload.get("state") or "UNKNOWN"
    render_status_pill(status, label=f"{label}: {status_label(status)}", st_module=st_module)


def status_summary(rows: list[Dict[str, Any]]) -> Dict[str, int]:
    summary: Dict[str, int] = {}
    for row in rows or []:
        status = normalize_status(row.get("status") or row.get("state") or row.get("health"))
        summary[status] = summary.get(status, 0) + 1
    return summary


def status_badge_html(status: Any, label: Optional[str] = None) -> str:
    norm = normalize_status(status)
    color = status_color(norm)
    text = label or status_label(norm)
    return (
        f'<span class="fx-pill">'
        f'<span class="fx-pill-dot" style="background:{color}; box-shadow:0 0 10px {color};"></span>'
        f'{text}</span>'
    )
