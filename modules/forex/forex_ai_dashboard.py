
from __future__ import annotations
from typing import Any, Dict

try:
    import streamlit as st
except Exception:
    st = None

from modules.forex.forex_ai_assistant import get_forex_ai_assistant


class ForexAIDashboard:

    def __init__(
        self,
        db=None,
        tenant_id=None,
        user_id=None,
        portfolio_id=None,
    ):
        self.db = db
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.portfolio_id = portfolio_id

        from modules.forex.forex_ai_orchestrator import (
            get_forex_ai_orchestrator,
        )

        self.ai = get_forex_ai_orchestrator(
            db=db,
        )


    def render(self):
        payload = self._payload()
        if st is None:
            return payload

        from modules.forex.ui.forex_ui_theme import inject_forex_ui_theme
        from modules.forex.ui.forex_ui_layout import render_page_header
        from modules.forex.ui.forex_ai_workspace import render_forex_ai_workspace

        inject_forex_ui_theme(st)
        render_page_header(
            "Forex AI & Quant Platform",
            "Institutional AI research, strategy intelligence, optimizer, and autonomous paper-trading controls.",
            icon="🧠",
        )
        return render_forex_ai_workspace(payload=payload, db=self.db)

    def _payload(self) -> Dict[str, Any]:
        try:
            briefing = self.ai.morning_brief()
        except Exception as exc:
            briefing = {
                "status": "WARNING",
                "error": str(exc),
            }
        payload = {
            "status": "READY" if not briefing.get("error") else "WARNING",

            "ai_assistant": briefing.get("briefing", {}),

            "market": briefing.get("market", {}),

            "strategy_lab": briefing.get(
                "briefing", {}
            ).get("strategy_lab", {}),

            "portfolio_optimizer": briefing.get(
                "briefing", {}
            ).get("portfolio_plan", {}),
        }
        try:
            from modules.forex.forex_ai_command_center import get_forex_ai_command_center
            payload["ai_command_center"] = get_forex_ai_command_center(db=self.db).briefing()
        except Exception as exc:
            payload["ai_command_center"] = {"status": "WARNING", "error": str(exc)}
        try:
            from modules.forex.forex_ai_investment_committee import get_forex_ai_investment_committee
            payload["ai_investment_committee"] = get_forex_ai_investment_committee(db=self.db).review(snapshot=payload)
        except Exception as exc:
            payload["ai_investment_committee"] = {"status": "WARNING", "error": str(exc)}
        try:
            from modules.forex.forex_ai_research_copilot import get_forex_ai_research_copilot
            payload["research_copilot"] = get_forex_ai_research_copilot(db=self.db).dashboard(snapshot=payload)
        except Exception as exc:
            payload["research_copilot"] = {"status": "WARNING", "error": str(exc)}
        return payload

    def run_autonomous_cycle(self, portfolio_id=None, user_id=None, tenant_id=None):
        return self.ai.autonomous_cycle(portfolio_id=portfolio_id, user_id=user_id, tenant_id=tenant_id)


_INSTANCE = None


def get_forex_ai_dashboard(
    db=None,
    tenant_id=None,
    user_id=None,
    portfolio_id=None,
):
    global _INSTANCE

    if (
        _INSTANCE is None
        or getattr(_INSTANCE, "db", None) is not db
        or getattr(_INSTANCE, "tenant_id", None) != tenant_id
        or getattr(_INSTANCE, "user_id", None) != user_id
        or getattr(_INSTANCE, "portfolio_id", None) != portfolio_id
    ):

        _INSTANCE = ForexAIDashboard(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )

    return _INSTANCE

def render_forex_ai_dashboard(
    db=None,
    tenant_id=None,
    user_id=None,
    portfolio_id=None,
    **kwargs,
):
    return get_forex_ai_dashboard(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
    ).render(**kwargs)
