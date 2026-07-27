"""
modules/forex/ui/forex_ui_kpi_demo.py

Demo for Phase 22.2 KPI/card components.
"""

from __future__ import annotations


def render_forex_ui_kpi_demo():
    import streamlit as st

    from modules.forex.ui.forex_ui_layout import render_page_header, panel
    from modules.forex.ui.forex_ui_metrics import build_trading_desk_kpis, render_kpi_grid
    from modules.forex.ui.forex_ui_cards import ForexMetricCard, render_metric_ribbon

    render_page_header(
        "Forex UI KPI Framework",
        "Reusable institutional KPI cards and metric formatting.",
        icon="📊",
    )

    snapshot = {
        "account": {
            "equity": 368452.17,
            "cash_balance": 125000,
            "margin_available": 242100,
            "margin_used": 45200,
        },
        "performance": {
            "daily_pnl": 2842.35,
            "daily_pnl_pct": 0.78,
            "total_unrealized_pnl": 1240.50,
            "unrealized_pnl_pct": 0.34,
        },
        "positions": [{"pair": "EUR/USD"}, {"pair": "USD/JPY"}, {"pair": "GBP/USD"}],
        "open_orders": [{"pair": "EUR/USD"}],
        "risk": {"risk_score": 82.5},
    }

    with panel("Trading Desk KPI Ribbon", kicker="Demo", meta="Phase 22.2"):
        render_kpi_grid(build_trading_desk_kpis(snapshot))

    with panel("Status KPI Cards", kicker="Reusable"):
        render_metric_ribbon([
            ForexMetricCard("Provider Health", "Healthy", "All providers online", status="HEALTHY", icon="🟢", progress=92),
            ForexMetricCard("AI Confidence", "92%", "Model consensus", status="READY", icon="🤖", progress=92),
            ForexMetricCard("Broker Safety", "Locked", "Live execution disabled", status="DISABLED", icon="🔒", progress=100),
            ForexMetricCard("Latency", "84 ms", "Average provider latency", status="READY", icon="⚡", progress=84),
        ])
