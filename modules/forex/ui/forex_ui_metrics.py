"""
modules/forex/ui/forex_ui_metrics.py

Sprint 22 — Phase 22.2
Metric helpers and KPI grids.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from modules.forex.ui.forex_ui_cards import ForexMetricCard, render_metric_ribbon


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str):
            cleaned = value.replace("$", "").replace(",", "").replace("%", "").strip()
            if cleaned in {"", "-", "—", "None"}:
                return default
            return float(cleaned)
        return float(value)
    except Exception:
        return default


def format_currency(value: Any, *, symbol: str = "$", decimals: int = 2, compact: bool = False) -> str:
    val = _safe_float(value)
    sign = "-" if val < 0 else ""
    val_abs = abs(val)

    if compact:
        if val_abs >= 1_000_000_000:
            return f"{sign}{symbol}{val_abs / 1_000_000_000:.{decimals}f}B"
        if val_abs >= 1_000_000:
            return f"{sign}{symbol}{val_abs / 1_000_000:.{decimals}f}M"
        if val_abs >= 1_000:
            return f"{sign}{symbol}{val_abs / 1_000:.{decimals}f}K"

    return f"{sign}{symbol}{val_abs:,.{decimals}f}"


def format_number(value: Any, *, decimals: int = 0, compact: bool = False) -> str:
    val = _safe_float(value)
    sign = "-" if val < 0 else ""
    val_abs = abs(val)

    if compact:
        if val_abs >= 1_000_000_000:
            return f"{sign}{val_abs / 1_000_000_000:.{decimals}f}B"
        if val_abs >= 1_000_000:
            return f"{sign}{val_abs / 1_000_000:.{decimals}f}M"
        if val_abs >= 1_000:
            return f"{sign}{val_abs / 1_000:.{decimals}f}K"

    return f"{val:,.{decimals}f}"


def format_percent(value: Any, *, decimals: int = 1, already_percent: bool = True) -> str:
    val = _safe_float(value)
    if not already_percent:
        val *= 100
    return f"{val:,.{decimals}f}%"


def format_metric_value(value: Any, metric_type: str = "number", **kwargs: Any) -> str:
    metric_type = str(metric_type or "number").lower()
    if metric_type in {"currency", "money", "dollar", "usd"}:
        return format_currency(value, **kwargs)
    if metric_type in {"percent", "percentage", "pct"}:
        return format_percent(value, **kwargs)
    if metric_type in {"int", "integer"}:
        return format_number(value, decimals=0, **kwargs)
    if metric_type in {"float", "decimal", "number"}:
        return format_number(value, decimals=kwargs.pop("decimals", 2), **kwargs)
    return str(value if value is not None else "-")


def infer_metric_direction(value: Any) -> str:
    val = _safe_float(value)
    if val > 0:
        return "positive"
    if val < 0:
        return "negative"
    return "neutral"


def metric_from_payload(
    payload: Dict[str, Any],
    *,
    key: str,
    label: str,
    metric_type: str = "number",
    caption: str = "",
    delta_key: Optional[str] = None,
    progress_key: Optional[str] = None,
    status_key: Optional[str] = None,
    icon: str = "",
    decimals: int = 2,
    compact: bool = False,
) -> ForexMetricCard:
    value = payload.get(key)
    formatted = format_metric_value(value, metric_type, decimals=decimals, compact=compact)
    delta = payload.get(delta_key) if delta_key else None
    progress = payload.get(progress_key) if progress_key else None
    status = payload.get(status_key) if status_key else None

    return ForexMetricCard(
        label=label,
        value=formatted,
        caption=caption,
        delta=delta,
        progress=progress,
        status=status,
        icon=icon,
    )


def build_account_kpis(account: Dict[str, Any], performance: Optional[Dict[str, Any]] = None) -> List[ForexMetricCard]:
    performance = performance or {}
    return [
        metric_from_payload(account, key="equity", label="Equity", metric_type="currency", caption="Portfolio value", icon="💼", compact=True),
        metric_from_payload(account, key="cash_balance", label="Cash", metric_type="currency", caption="Available cash", icon="💵", compact=True),
        metric_from_payload(account, key="margin_available", label="Buying Power", metric_type="currency", caption="Margin available", icon="⚡", compact=True),
        metric_from_payload(account, key="margin_used", label="Margin Used", metric_type="currency", caption="Current margin", icon="📊", compact=True),
        ForexMetricCard(
            label="Daily P/L",
            value=format_currency(performance.get("daily_pnl", performance.get("total_pnl", 0)), compact=True),
            caption="Session performance",
            delta=performance.get("daily_pnl_pct"),
            icon="📈",
            progress=min(abs(_safe_float(performance.get("daily_pnl_pct"))) * 10, 100),
        ),
    ]


def build_trading_desk_kpis(snapshot: Dict[str, Any]) -> List[ForexMetricCard]:
    account = snapshot.get("account") or {}
    performance = snapshot.get("performance") or {}
    positions = snapshot.get("positions") or []
    orders = snapshot.get("open_orders") or snapshot.get("orders") or []
    risk = snapshot.get("risk") or {}

    return [
        ForexMetricCard("Open Positions", format_number(len(positions), decimals=0), "Active exposure", icon="📌", progress=min(len(positions) * 10, 100)),
        ForexMetricCard("Active Orders", format_number(len(orders), decimals=0), "Working orders", icon="🧾", progress=min(len(orders) * 12, 100)),
        ForexMetricCard("Equity", format_currency(account.get("equity", 0), compact=True), "Portfolio value", icon="💼", progress=75),
        ForexMetricCard("Unrealized P/L", format_currency(performance.get("total_unrealized_pnl", 0), compact=True), "Open trade P/L", delta=performance.get("unrealized_pnl_pct"), icon="📈"),
        ForexMetricCard("Risk Score", format_number(risk.get("risk_score", 0), decimals=1), "Institutional risk", icon="🛡️", progress=risk.get("risk_score", 0), status="READY" if _safe_float(risk.get("risk_score", 0)) >= 70 else "WARNING"),
    ]


def render_kpi_grid(
    cards: Iterable[ForexMetricCard | Dict[str, Any]],
    *,
    st_module: Optional[Any] = None,
) -> None:
    render_metric_ribbon(cards, st_module=st_module)
