"""
modules/forex/forex_terminal_snapshot_builder.py

Sprint 26
Phase 1

Unified Forex Terminal Snapshot Builder

This is the ONLY object responsible for assembling the
institutional ForexTerminalSnapshot.

No UI.
No Streamlit.
No session state.

Trading Desk
Portfolio Dashboard
Risk Dashboard
Performance Dashboard
Execution Center

all consume the same immutable snapshot.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from modules.forex.forex_portfolio_engine import (
    get_forex_portfolio_engine,
)

from modules.forex.forex_terminal_snapshot_models import (
    ForexTerminalSnapshot,
    TerminalAccount,
    TerminalPortfolio,
    TerminalPosition,
    TerminalOrder,
    TerminalExecution,
    TerminalPerformance,
    TerminalRisk,
    TerminalExposure,
    TerminalProviderHealth,
    TerminalDiagnostics,
)

logger = logging.getLogger(__name__)


# =====================================================================
# helpers
# =====================================================================

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_dict(value) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _safe_list(value) -> List[Any]:
    if isinstance(value, list):
        return value
    return []


def _filter_fields(model_cls, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Removes unknown fields before constructing dataclasses.

    Allows snapshot models to evolve without breaking builder.
    """

    if not isinstance(payload, dict):
        return {}

    allowed = getattr(model_cls, "__dataclass_fields__", {}).keys()

    return {
        k: v
        for k, v in payload.items()
        if k in allowed
    }


# =====================================================================
# Builder
# =====================================================================

class ForexTerminalSnapshotBuilder:

    """
    Unified snapshot assembler.

    Everything the Trading Desk displays originates here.
    """

    def __init__(
        self,
        *,
        db=None,
        runtime=None,
    ):

        self.db = db
        self.runtime = runtime

    # =================================================================

    def build(
        self,
        *,
        tenant_id: Optional[str],
        user_id: Optional[str],
        portfolio_id: Optional[str],
        refresh: bool = False,
        persist: bool = False,
    ) -> ForexTerminalSnapshot:

        engine = get_forex_portfolio_engine(

            db=self.db,

            tenant_id=tenant_id,

            user_id=user_id,

            portfolio_id=portfolio_id,

        )

        terminal = engine.get_terminal_snapshot(

            refresh=refresh,

            persist=persist,

        )

        if hasattr(terminal, "to_dict"):
            terminal = terminal.to_dict()

        terminal = _safe_dict(terminal)

        account = self._build_account(
            terminal.get("account", {})
        )

        portfolio = self._build_portfolio(
            terminal.get("portfolio", {})
        )

        positions = self._build_positions(
            terminal.get("positions", [])
        )

        open_orders = self._build_orders(
            terminal.get("open_orders", [])
        )

        filled_orders = self._build_orders(
            terminal.get("filled_orders", [])
        )

        executions = self._build_executions(
            terminal.get("execution_history", [])
        )

        performance = self._build_performance(
            terminal.get("performance", {})
        )

        risk = self._build_risk(
            terminal.get("risk", {})
        )

        exposure = self._build_exposure(
            terminal
        )

        provider = self._build_provider_health()

        diagnostics = self._build_diagnostics()

        snapshot = ForexTerminalSnapshot(

            runtime_id=getattr(
                self.runtime,
                "runtime_id",
                "",
            ),

            generated_at=_utc_now(),

            tenant_id=tenant_id,

            user_id=user_id,

            portfolio_id=portfolio_id,

            account=account,

            portfolio=portfolio,

            positions=positions,

            open_orders=open_orders,

            filled_orders=filled_orders,

            executions=executions,

            cash_ledger=_safe_list(
                terminal.get("cash_ledger")
            ),

            performance=performance,

            risk=risk,

            exposure=exposure,

            provider_health=provider,

            executive_ai=_safe_dict(
                terminal.get("executive_ai")
            ),

            strategy=_safe_dict(
                terminal.get("strategy")
            ),

            diagnostics=diagnostics,

            system=_safe_dict(
                terminal.get("system")
            ),

            metadata=_safe_dict(
                terminal.get("metadata")
            ),

        )

        return snapshot

    # =================================================================
    # builders
    # =================================================================

    def _build_account(self, payload):

        return TerminalAccount(

            **_filter_fields(
                TerminalAccount,
                _safe_dict(payload),
            )

        )

    # -----------------------------------------------------------------

    def _build_portfolio(self, payload):

        return TerminalPortfolio(

            **_filter_fields(
                TerminalPortfolio,
                _safe_dict(payload),
            )

        )

    # -----------------------------------------------------------------

    def _build_positions(self, rows):

        output = []

        for row in _safe_list(rows):

            try:

                output.append(

                    TerminalPosition(

                        **_filter_fields(
                            TerminalPosition,
                            row,
                        )

                    )

                )

            except Exception as exc:

                logger.warning(
                    "Position skipped: %s",
                    exc,
                )

        return output

    # -----------------------------------------------------------------

    def _build_orders(self, rows):

        output = []

        for row in _safe_list(rows):

            try:

                output.append(

                    TerminalOrder(

                        **_filter_fields(
                            TerminalOrder,
                            row,
                        )

                    )

                )

            except Exception as exc:

                logger.warning(
                    "Order skipped: %s",
                    exc,
                )

        return output

    # -----------------------------------------------------------------

    def _build_executions(self, rows):

        output = []

        for row in _safe_list(rows):

            try:

                output.append(

                    TerminalExecution(

                        **_filter_fields(
                            TerminalExecution,
                            row,
                        )

                    )

                )

            except Exception as exc:

                logger.warning(
                    "Execution skipped: %s",
                    exc,
                )

        return output

    # -----------------------------------------------------------------

    def _build_performance(self, payload):

        return TerminalPerformance(

            **_filter_fields(
                TerminalPerformance,
                _safe_dict(payload),
            )

        )

    # -----------------------------------------------------------------

    def _build_risk(self, payload):

        return TerminalRisk(

            **_filter_fields(
                TerminalRisk,
                _safe_dict(payload),
            )

        )

    # -----------------------------------------------------------------

    def _build_exposure(self, terminal):

        portfolio = _safe_dict(
            terminal.get("portfolio")
        )

        return TerminalExposure(

            currency_exposure=_safe_list(
                terminal.get("currency_exposure")
            ),

            pair_exposure=_safe_list(
                terminal.get("pair_exposure")
            ),

            gross_exposure=portfolio.get(
                "gross_exposure",
                0.0,
            ),

            net_exposure=portfolio.get(
                "net_exposure",
                0.0,
            ),

        )

    # -----------------------------------------------------------------

    def _build_provider_health(self):

        runtime = self.runtime

        return TerminalProviderHealth(

            providers=getattr(
                runtime,
                "provider_health",
                [],
            ),

            runtime_health=getattr(
                runtime,
                "runtime_health",
                100.0,
            ),

            failed_providers=getattr(
                runtime,
                "failed_providers",
                [],
            ),

            provider_usage=getattr(
                runtime,
                "provider_usage",
                {},
            ),

            provider_latency=getattr(
                runtime,
                "provider_latency",
                {},
            ),

        )

    # -----------------------------------------------------------------

    def _build_diagnostics(self):

        runtime = self.runtime

        return TerminalDiagnostics(

            runtime_id=getattr(
                runtime,
                "runtime_id",
                "",
            ),

            generated_at=_utc_now(),

            build_ms=getattr(
                runtime,
                "runtime_total_ms",
                getattr(
                    runtime,
                    "runtime_ms",
                    0.0,
                ),
            ),

            diagnostics=getattr(
                runtime,
                "diagnostics",
                {},
            ),

        )


# =====================================================================
# singleton
# =====================================================================

_BUILDER = None


def get_forex_terminal_snapshot_builder(
    *,
    db=None,
    runtime=None,
):

    global _BUILDER

    if (
        _BUILDER is None
        or _BUILDER.db is not db
        or _BUILDER.runtime is not runtime
    ):

        _BUILDER = ForexTerminalSnapshotBuilder(

            db=db,

            runtime=runtime,

        )

    return _BUILDER