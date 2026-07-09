"""
modules/execution/execution_context_validator.py

Sprint 26
Institutional Execution Framework

Execution Context Validator

Validates execution requests before entering the execution
pipeline.

Unlike ExecutionEventValidator, this validator operates on an
ExecutionContext and returns structured validation results
instead of raising exceptions.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .execution_context import ExecutionContext


class ExecutionContextValidator:
    """Validates ExecutionContext objects prior to execution."""

    def __init__(self, repository=None, query=None):
        self.repository = repository
        self.query = query

    # ==========================================================
    # Public
    # ==========================================================

    def validate(self, context: ExecutionContext) -> Dict[str, Any]:
        errors: List[str] = []
        warnings: List[str] = []

        self._validate_account(context, errors)
        self._validate_portfolio(context, errors)
        self._validate_symbol(context, errors)
        self._validate_side(context, errors)
        self._validate_quantity(context, errors)
        self._validate_prices(context, errors, warnings)
        self._validate_order_type(context, errors)
        self._validate_leverage(context, warnings)
        self._validate_position(context, warnings)

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "message": (
                "Validation successful."
                if not errors
                else "Execution validation failed."
            ),
        }

    # ==========================================================
    # Account
    # ==========================================================

    def _validate_account(
        self,
        context: ExecutionContext,
        errors: List[str],
    ):

        if not context.account_id:
            errors.append("Account ID is required.")

    # ==========================================================
    # Portfolio
    # ==========================================================

    def _validate_portfolio(
        self,
        context: ExecutionContext,
        errors: List[str],
    ):

        if not context.portfolio_id:
            errors.append("Portfolio ID is required.")

    # ==========================================================
    # Symbol
    # ==========================================================

    def _validate_symbol(
        self,
        context: ExecutionContext,
        errors: List[str],
    ):

        if not (context.symbol or context.pair):
            errors.append("Trading symbol is required.")

    # ==========================================================
    # Side
    # ==========================================================

    def _validate_side(
        self,
        context: ExecutionContext,
        errors: List[str],
    ):

        if context.side is None:
            errors.append("Order side is required.")
            return

        side = str(context.side).upper()

        if side not in {
            "BUY",
            "SELL",
            "LONG",
            "SHORT",
        }:
            errors.append(f"Invalid order side '{context.side}'.")

    # ==========================================================
    # Quantity
    # ==========================================================

    def _validate_quantity(
        self,
        context: ExecutionContext,
        errors: List[str],
    ):

        qty = context.units or context.quantity

        try:
            qty = float(qty)
        except Exception:
            qty = 0

        if qty <= 0:
            errors.append("Quantity must be greater than zero.")

    # ==========================================================
    # Prices
    # ==========================================================

    def _validate_prices(
        self,
        context: ExecutionContext,
        errors: List[str],
        warnings: List[str],
    ):

        order_type = str(context.order_type or "MARKET").upper()

        if order_type != "MARKET":
            if context.requested_price is None:
                errors.append("Limit/Stop price required.")

        if (
            context.stop_price is not None
            and context.stop_price <= 0
        ):
            errors.append("Stop price must be positive.")

        if (
            context.target_price is not None
            and context.target_price <= 0
        ):
            errors.append("Target price must be positive.")

        if (
            context.stop_price is not None
            and context.target_price is not None
            and context.stop_price == context.target_price
        ):
            warnings.append(
                "Stop price equals target price."
            )

    # ==========================================================
    # Order Type
    # ==========================================================

    def _validate_order_type(
        self,
        context: ExecutionContext,
        errors: List[str],
    ):

        valid = {
            "MARKET",
            "LIMIT",
            "STOP",
            "STOP_LIMIT",
            "TRAILING_STOP",
            "MKT",
        }

        order_type = str(
            context.order_type or "MARKET"
        ).upper()

        if order_type not in valid:
            errors.append(
                f"Unsupported order type '{order_type}'."
            )

    # ==========================================================
    # Leverage
    # ==========================================================

    def _validate_leverage(
        self,
        context: ExecutionContext,
        warnings: List[str],
    ):

        if context.leverage is None:
            return

        try:
            lev = float(context.leverage)

            if lev <= 0:
                warnings.append(
                    "Leverage should be greater than zero."
                )

            if lev > 100:
                warnings.append(
                    "High leverage detected."
                )

        except Exception:
            warnings.append(
                "Unable to validate leverage."
            )

    # ==========================================================
    # Existing Position
    # ==========================================================

    def _validate_position(
        self,
        context: ExecutionContext,
        warnings: List[str],
    ):

        if context.position_id:
            warnings.append(
                "Execution references an existing position."
            )

    # ==========================================================
    # Convenience
    # ==========================================================

    @staticmethod
    def is_valid(result: Dict[str, Any]) -> bool:
        return bool(result.get("valid", False))

    @staticmethod
    def validation_errors(result: Dict[str, Any]) -> List[str]:
        return result.get("errors", [])

    @staticmethod
    def validation_warnings(result: Dict[str, Any]) -> List[str]:
        return result.get("warnings", [])