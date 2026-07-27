"""
modules/execution/execution_snapshot_pipeline.py

Sprint 26
Institutional Execution Framework

Execution Snapshot Pipeline

Responsible for:

• Terminal snapshot refresh
• Portfolio snapshot refresh
• Dashboard synchronization
• Execution verification
• Recent activity updates
• Execution history updates
• Audit synchronization

Shared by:

    Forex
    Equities
    Options
    Crypto
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from .execution_context import ExecutionContext


class ExecutionSnapshotPipeline:
    """
    Institutional snapshot pipeline.

    This class owns every snapshot update after an
    execution lifecycle event.

    No execution pipeline should call the portfolio
    engine snapshot methods directly.
    """

    def __init__(
        self,
        *,
        portfolio_engine,
        execution_repository,
        execution_query,
    ):
        self.portfolio_engine = portfolio_engine
        self.execution_repository = execution_repository
        self.execution_query = execution_query

    # ==========================================================
    # Main Refresh
    # ==========================================================

    def refresh(
        self,
        context: ExecutionContext,
    ) -> ExecutionContext:

        try:

            snapshot = self.refresh_terminal_snapshot(
                context
            )

            context.set_snapshot(snapshot)

            try:

                self.refresh_portfolio_snapshot(
                    context
                )

            except Exception as exc:

                context.add_warning(
                    f"Portfolio snapshot refresh failed: {exc}"
                )

        except Exception as exc:

            context.add_warning(
                f"Terminal snapshot refresh failed: {exc}"
            )

        try:
            self.refresh_execution_history(context)
        except Exception as exc:
            context.add_warning(
                f"Execution history refresh failed: {exc}"
            )

        try:
            self.refresh_recent_activity(context)
        except Exception as exc:
            context.add_warning(
                f"Recent activity refresh failed: {exc}"
            )

        try:
            self.refresh_dashboard(context)
        except Exception as exc:
            context.add_warning(
                f"Dashboard refresh failed: {exc}"
            )

        context.snapshot_refreshed_at = (
            datetime.utcnow()
        )



        return context

    # ==========================================================
    # Terminal Snapshot
    # ==========================================================

    def refresh_terminal_snapshot(
        self,
        context: ExecutionContext,
    ) -> Optional[Dict]:

        snapshot = self.portfolio_engine.get_terminal_snapshot(

            account_id=context.account_id,

            portfolio_id=context.portfolio_id,

            refresh=True,

            persist=True,

            include_orders=True,

            include_history=True,

        )

        if hasattr(snapshot, "to_dict"):

            snapshot = snapshot.to_dict()

        return snapshot

    # ==========================================================
    # Portfolio Snapshot
    # ==========================================================

    def refresh_portfolio_snapshot(
        self,
        context: ExecutionContext,
    ) -> None:

        if hasattr(
            self.portfolio_engine,
            "refresh_portfolio_snapshot",
        ):

            self.portfolio_engine.refresh_portfolio_snapshot(

                portfolio_id=context.portfolio_id

            )

    # ==========================================================
    # Execution History
    # ==========================================================

    def refresh_execution_history(
        self,
        context: ExecutionContext,
    ) -> None:

        if hasattr(
            self.execution_repository,
            "rebuild_execution_history",
        ):

            self.execution_repository.rebuild_execution_history(

                portfolio_id=context.portfolio_id,

                account_id=context.account_id,

            )

    # ==========================================================
    # Recent Activity
    # ==========================================================

    def refresh_recent_activity(
        self,
        context: ExecutionContext,
    ) -> None:

        if hasattr(
            self.execution_repository,
            "refresh_recent_activity",
        ):

            self.execution_repository.refresh_recent_activity(

                portfolio_id=context.portfolio_id,

                account_id=context.account_id,

            )

    # ==========================================================
    # Dashboard
    # ==========================================================

    def refresh_dashboard(
        self,
        context: ExecutionContext,
    ) -> None:

        if hasattr(
            self.portfolio_engine,
            "refresh_dashboard",
        ):

            self.portfolio_engine.refresh_dashboard(

                portfolio_id=context.portfolio_id,

                account_id=context.account_id,

            )

    # ==========================================================
    # Verification
    # ==========================================================

    def verify(
        self,
        context: ExecutionContext,
    ) -> bool:

        checks = self.verify_execution(context)

        return checks["verified"]

    def verify_execution(
        self,
        context: ExecutionContext,
    ) -> Dict[str, Any]:

        checks = {

            "order": False,

            "position": False,

            "snapshot": False,

            "events": False,

        }

        #
        # Order
        #

        if hasattr(
            self.execution_query,
            "order_exists",
        ):

            checks["order"] = self.execution_query.order_exists(

                broker_order_id=context.broker_order_id

            )

        #
        # Position
        #

        if hasattr(
            self.execution_query,
            "position_exists",
        ):

            checks["position"] = self.execution_query.position_exists(

                position_id=context.position_id

            )

        #
        # Snapshot
        #

        checks["snapshot"] = (
            context.snapshot is not None
        )

        #
        # Events
        #

        checks["events"] = bool(
            getattr(
                context,
                "event_ids",
                {},
            )
        )

        verified = all(checks.values())

        verification = {
            "verified": verified,
            "checks": checks,
            "verified_at": datetime.utcnow().isoformat(),
        }

        context.set_verification(
            verification
        )

        return verification

    # ==========================================================
    # Audit
    # ==========================================================

    def synchronize_audit(
        self,
        context: ExecutionContext,
    ) -> None:

        if hasattr(
            self.execution_repository,
            "synchronize_audit",
        ):

            self.execution_repository.synchronize_audit(

                execution_id=context.execution_id,

                correlation_id=context.correlation_id,

            )

    # ==========================================================
    # Replay Cache
    # ==========================================================

    def update_replay_cache(
        self,
        context: ExecutionContext,
    ) -> None:

        if hasattr(
            self.execution_repository,
            "update_replay_cache",
        ):

            self.execution_repository.update_replay_cache(

                execution_id=context.execution_id,

                correlation_id=context.correlation_id,

            )

    # ==========================================================
    # Attribution Cache
    # ==========================================================

    def update_attribution_cache(
        self,
        context: ExecutionContext,
    ) -> None:

        if hasattr(
            self.execution_repository,
            "update_attribution_cache",
        ):

            self.execution_repository.update_attribution_cache(

                execution_id=context.execution_id,

                portfolio_id=context.portfolio_id,

            )

    # ==========================================================
    # Compliance Cache
    # ==========================================================

    def update_compliance_cache(
        self,
        context: ExecutionContext,
    ) -> None:

        if hasattr(
            self.execution_repository,
            "update_compliance_cache",
        ):

            self.execution_repository.update_compliance_cache(

                execution_id=context.execution_id,

                correlation_id=context.correlation_id,

            )

    # ==========================================================
    # Full Synchronization
    # ==========================================================

    def synchronize(
        self,
        context: ExecutionContext,
    ) -> ExecutionContext:

        context = self.refresh(context)

        try:
            self.synchronize_audit(context)
        except Exception as exc:
            context.add_warning(
                f"Audit synchronization failed: {exc}"
            )
        try:
            self.update_replay_cache(context)
        except Exception as exc:
            context.add_warning(
                f"Update replay cache failed: {exc}"
            )
        try:
            self.update_attribution_cache(context)
        except Exception as exc:
            context.add_warning(
                f"Update attribution cache failed: {exc}"
            )

        try:
            self.update_compliance_cache(context)
        except Exception as exc:
            context.add_warning(
                f"Update compliance cache failed: {exc}"
            )

        context.synchronized_at = (
            datetime.utcnow()
        )
        return context