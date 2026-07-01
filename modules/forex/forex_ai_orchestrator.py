"""
modules/forex/forex_ai_orchestrator.py

Sprint 25 Runtime-Aware AI Orchestrator.

Responsibilities
----------------
• Produce the morning institutional briefing.
• Coordinate AI Assistant.
• Refresh market data before autonomous execution.
• Support the shared RuntimeContext while remaining fully
  backward compatible with older modules.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from modules.forex.forex_ai_assistant import (
    get_forex_ai_assistant,
)
from modules.forex.forex_service import (
    get_forex_service,
)


class ForexAIOrchestrator:

    def __init__(self, db=None):

        self.db = db

        self.ai = get_forex_ai_assistant(db=db)

        #
        # Forex service is already a singleton.
        #
        self.service = get_forex_service(db=db)

    # ---------------------------------------------------------
    # Morning Brief
    # ---------------------------------------------------------

    def morning_brief(
        self,
        runtime=None,
        force_refresh: bool = False,
    ):

        #
        # Market Snapshot
        #
        try:

            market = self.service.get_command_center()

        except Exception as exc:

            market = {
                "status": "WARNING",
                "error": str(exc),
            }

        #
        # AI Briefing
        #
        try:

            briefing = self.ai.daily_briefing(
                runtime=runtime,
                force_refresh=force_refresh,
            )

        except TypeError:
            #
            # Backwards compatibility with older AI Assistant.
            #
            briefing = self.ai.daily_briefing()

        except Exception as exc:

            briefing = {
                "status": "WARNING",
                "error": str(exc),
            }

        #
        # Runtime diagnostics
        #
        runtime_summary = {}

        if runtime is not None and hasattr(runtime, "summary"):

            try:
                runtime_summary = runtime.summary()
            except Exception:
                runtime_summary = {}

        return {

            "generated_at": datetime.now(timezone.utc).isoformat(),

            "market": market,

            "briefing": briefing,

            #
            # Sprint 25 Diagnostics
            #
            "runtime": runtime_summary,

            "runtime_source": (
                "shared"
                if runtime is not None
                else "local"
            ),
        }

    # ---------------------------------------------------------
    # Autonomous Cycle
    # ---------------------------------------------------------

    def autonomous_cycle(
        self,
        runtime=None,
        portfolio_id: Optional[str] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        force_refresh: bool = False,
    ):

        #
        # Refresh market data before execution.
        #
        try:

            self.service.refresh_market_data(
                force_refresh=force_refresh,
            )

        except TypeError:
            #
            # Older refresh implementation.
            #
            self.service.refresh_market_data()

        #
        # Execute AI trading cycle.
        #
        return self.ai.execute(
            portfolio_id=portfolio_id,
            user_id=user_id,
            tenant_id=tenant_id,
        )


_ORCH = None


def get_forex_ai_orchestrator(db=None):

    global _ORCH

    if _ORCH is None:

        _ORCH = ForexAIOrchestrator(db=db)

    return _ORCH