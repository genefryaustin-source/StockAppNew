"""
modules/forex/forex_institutional_workspace.py

Institutional workspace wrapper with cycle-safe imports and
Sprint 25 runtime-aware execution.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


class ForexInstitutionalWorkspace:

    def __init__(self, db=None):
        self.db = db

    def snapshot(
        self,
        runtime=None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:

        data: Dict[str, Any] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "READY",
        }

        #
        # Institutional Terminal
        #
        try:

            from modules.forex.forex_institutional_terminal import (
                get_forex_institutional_terminal,
            )

            terminal = get_forex_institutional_terminal(db=self.db)

            try:
                data["terminal"] = terminal.snapshot(
                    runtime=runtime,
                    force_refresh=force_refresh,
                )
            except TypeError:
                data["terminal"] = terminal.snapshot()

        except Exception as exc:

            data["terminal"] = {
                "status": "WARNING",
                "error": str(exc),
            }

        #
        # Strategy Lab
        #
        try:

            from modules.forex.forex_strategy_lab import (
                get_forex_strategy_lab,
            )

            data["strategy_lab"] = (
                get_forex_strategy_lab(db=self.db).run(
                    runtime=runtime,
                    force_refresh=force_refresh,
                )
            )

        except Exception as exc:

            data["strategy_lab"] = {
                "status": "WARNING",
                "error": str(exc),
            }

        #
        # Portfolio Optimizer
        #
        try:

            from modules.forex.forex_portfolio_optimizer import (
                get_forex_portfolio_optimizer,
            )

            data["portfolio_optimizer"] = (
                get_forex_portfolio_optimizer(db=self.db).optimize(
                    runtime=runtime,
                    force_refresh=force_refresh,
                )
            )

        except Exception as exc:

            data["portfolio_optimizer"] = {
                "status": "WARNING",
                "error": str(exc),
            }

        #
        # AI Orchestrator
        #
        try:

            from modules.forex.forex_ai_orchestrator import (
                get_forex_ai_orchestrator,
            )

            orchestrator = get_forex_ai_orchestrator(db=self.db)

            try:

                data["ai_briefing"] = orchestrator.morning_brief(
                    runtime=runtime,
                    force_refresh=force_refresh,
                )

            except TypeError:

                #
                # Older implementation
                #
                data["ai_briefing"] = orchestrator.morning_brief()

        except Exception as exc:

            data["ai_briefing"] = {
                "status": "WARNING",
                "error": str(exc),
            }

        #
        # Sprint 25 Runtime Diagnostics
        #
        if runtime is not None and hasattr(runtime, "summary"):

            try:
                data["runtime"] = runtime.summary()
            except Exception:
                data["runtime"] = {}

        else:

            data["runtime"] = {}

        data["runtime_source"] = (
            "shared"
            if runtime is not None
            else "local"
        )

        return data

    def refresh(self):

        try:

            from modules.forex.forex_service import (
                get_forex_service,
            )

            return get_forex_service(
                db=self.db,
            ).refresh_market_data()

        except Exception as exc:

            return {
                "status": "ERROR",
                "error": str(exc),
            }

    def render(self, *args: Any, **kwargs: Any):

        try:

            from modules.forex.forex_institutional_command_center import (
                render_forex_institutional_command_center,
            )

            kwargs.setdefault("db", self.db)

            return render_forex_institutional_command_center(
                *args,
                **kwargs,
            )

        except Exception as exc:

            try:

                import streamlit as st

                st.error(
                    f"Forex institutional workspace failed: {exc}"
                )

            except Exception:
                pass

            return {
                "status": "ERROR",
                "error": str(exc),
            }


_INSTANCE = None


def get_forex_institutional_workspace(db=None):

    global _INSTANCE

    if _INSTANCE is None or (
        db is not None and _INSTANCE.db is None
    ):

        _INSTANCE = ForexInstitutionalWorkspace(db=db)

    return _INSTANCE


def render_forex_institutional_workspace(
    *args: Any,
    **kwargs: Any,
):

    db = kwargs.get("db")

    if db is None and args:
        db = args[0]

    return get_forex_institutional_workspace(
        db=db,
    ).render(
        *args,
        **kwargs,
    )