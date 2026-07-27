"""
api/services/forex_position_management_api_service.py

Forex Position Management API Service

Backs POST /api/v1/forex/positions/{id}/close,
POST /api/v1/forex/positions/{id}/reverse,
PUT /api/v1/forex/positions/{id} (modify stop/target), and
POST /api/v1/forex/positions/flatten.

Wraps modules.forex.forex_position_management_engine.
ForexPositionManagementEngine -- close_position, reverse_position,
modify_position, flatten_account. No business logic lives here.

Only exposes the four operations confirmed working end-to-end during
this build: close, reverse, modify (stop/target), flatten. scale_in/
scale_out are deliberately NOT exposed here -- they route through the
same shared modules.execution.execution_position_pipeline.
ExecutionPositionPipeline.modify(), which only supports stop_price/
target_price, not quantity changes. That's a real gap in shared,
cross-asset-class code (forex/equities/options/crypto all use this
pipeline), not something to patch around at this layer.

Position ownership is verified here before any operation:
ExecutionPositionRepository.load_position() itself has no tenant_id
filter, so a caller could otherwise operate on any tenant's position
by guessing its id.
"""

from __future__ import annotations

import logging
from typing import Any

from api.services._forex_portfolio_resolution import resolve_forex_portfolio_id

logger = logging.getLogger(__name__)


class ForexPositionManagementAPIService:
    """API service for forex position lifecycle operations (close, reverse, modify, flatten)."""

    def __init__(self, db):
        self.db = db

    # ---------------------------------------------------------
    # Internal
    # ---------------------------------------------------------

    def _load_owned_position(self, *, tenant_id: str, position_id: str) -> dict[str, Any] | None:
        """Raw position row, scoped to tenant_id. None if not found or owned by a different tenant."""
        try:
            from modules.execution.execution_position_repository import (
                ExecutionPositionRepository,
            )

            repo = ExecutionPositionRepository(db=self.db)
            position = repo.load_position(position_id)

        except Exception:
            logger.exception("Failed to load forex position | position_id=%s", position_id)
            try:
                self.db.rollback()
            except Exception:
                pass
            return None

        if position is None or position.get("tenant_id") != tenant_id:
            return None

        return position

    def _engine(self, *, tenant_id: str, user_id: str | None, portfolio_id: str):
        from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine
        from modules.forex.forex_position_management_engine import (
            ForexPositionManagementEngine,
        )

        pf_engine = get_forex_portfolio_engine(
            tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id, db=self.db,
        )
        pf_engine.ensure_tables()
        self.db.commit()

        return ForexPositionManagementEngine(db=self.db, portfolio_engine=pf_engine)

    @staticmethod
    def _serialize_context(ctx: Any) -> dict[str, Any]:
        position = getattr(ctx, "position", None)
        return {
            "status": getattr(ctx, "status", None),
            "message": getattr(ctx, "message", None),
            "position_id": getattr(ctx, "position_id", None),
            "position": position.to_dict() if position is not None and hasattr(position, "to_dict") else None,
            "errors": list(getattr(ctx, "errors", []) or []),
            "warnings": list(getattr(ctx, "warnings", []) or []),
        }

    # ---------------------------------------------------------
    # Close
    # ---------------------------------------------------------

    def close_position(
        self,
        *,
        tenant_id: str,
        user_id: str | None,
        position_id: str,
        quantity: float | None = None,
        exit_price: float | None = None,
    ) -> dict[str, Any] | None:
        """
        Close a position (fully, or partially if quantity is given and
        less than the open size). Returns None if the position doesn't
        exist or doesn't belong to tenant_id, which the router turns
        into a 404.
        """

        position = self._load_owned_position(tenant_id=tenant_id, position_id=position_id)
        if position is None:
            return None

        try:
            engine = self._engine(
                tenant_id=tenant_id, user_id=user_id, portfolio_id=position.get("portfolio_id"),
            )
            ctx = engine.close_position(position_id, quantity=quantity, requested_price=exit_price)
            return self._serialize_context(ctx)

        except Exception:
            logger.exception("Failed to close forex position | position_id=%s", position_id)
            try:
                self.db.rollback()
            except Exception:
                pass
            return {
                "status": "ERROR",
                "message": "Close failed due to an internal error.",
                "position_id": position_id,
                "position": None,
                "errors": ["internal_error"],
                "warnings": [],
            }

    # ---------------------------------------------------------
    # Reverse
    # ---------------------------------------------------------

    def reverse_position(
        self,
        *,
        tenant_id: str,
        user_id: str | None,
        position_id: str,
    ) -> dict[str, Any] | None:
        """Close a position and immediately open the opposite side. None if not found/not owned."""

        position = self._load_owned_position(tenant_id=tenant_id, position_id=position_id)
        if position is None:
            return None

        try:
            engine = self._engine(
                tenant_id=tenant_id, user_id=user_id, portfolio_id=position.get("portfolio_id"),
            )
            ctx = engine.reverse_position(position_id)
            return self._serialize_context(ctx)

        except Exception:
            logger.exception("Failed to reverse forex position | position_id=%s", position_id)
            try:
                self.db.rollback()
            except Exception:
                pass
            return {
                "status": "ERROR",
                "message": "Reverse failed due to an internal error.",
                "position_id": position_id,
                "position": None,
                "errors": ["internal_error"],
                "warnings": [],
            }

    # ---------------------------------------------------------
    # Modify (stop / target)
    # ---------------------------------------------------------

    def modify_position(
        self,
        *,
        tenant_id: str,
        user_id: str | None,
        position_id: str,
        stop_price: float | None = None,
        target_price: float | None = None,
    ) -> dict[str, Any] | None:
        """Update stop-loss/take-profit. None fields are left unchanged, not cleared."""

        position = self._load_owned_position(tenant_id=tenant_id, position_id=position_id)
        if position is None:
            return None

        try:
            engine = self._engine(
                tenant_id=tenant_id, user_id=user_id, portfolio_id=position.get("portfolio_id"),
            )
            ctx = engine.modify_position(position_id, stop_price=stop_price, target_price=target_price)
            return self._serialize_context(ctx)

        except Exception:
            logger.exception("Failed to modify forex position | position_id=%s", position_id)
            try:
                self.db.rollback()
            except Exception:
                pass
            return {
                "status": "ERROR",
                "message": "Modify failed due to an internal error.",
                "position_id": position_id,
                "position": None,
                "errors": ["internal_error"],
                "warnings": [],
            }

    # ---------------------------------------------------------
    # Flatten
    # ---------------------------------------------------------

    def flatten_account(
        self,
        *,
        tenant_id: str,
        user_id: str | None,
        portfolio_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Close every open position in a portfolio's account. portfolio_id
        is optional -- omit it to use the caller's default portfolio.
        """

        resolved_portfolio_id = resolve_forex_portfolio_id(
            self.db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id,
        )

        try:
            from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine

            pf_engine = get_forex_portfolio_engine(
                tenant_id=tenant_id, user_id=user_id, portfolio_id=resolved_portfolio_id, db=self.db,
            )
            pf_engine.ensure_tables()
            self.db.commit()

            account = pf_engine.get_or_create_account(portfolio_id=resolved_portfolio_id)

            engine = self._engine(
                tenant_id=tenant_id, user_id=user_id, portfolio_id=resolved_portfolio_id,
            )
            results = engine.flatten_account(account_id=account.id)

        except Exception:
            logger.exception(
                "Failed to flatten forex account | tenant_id=%s portfolio_id=%s",
                tenant_id, resolved_portfolio_id,
            )
            try:
                self.db.rollback()
            except Exception:
                pass
            return {
                "portfolio_id": resolved_portfolio_id,
                "closed_count": 0,
                "results": [],
                "error": "Flatten failed due to an internal error.",
            }

        serialized = [self._serialize_context(ctx) for ctx in (results or [])]

        return {
            "portfolio_id": resolved_portfolio_id,
            "closed_count": len(serialized),
            "results": serialized,
        }