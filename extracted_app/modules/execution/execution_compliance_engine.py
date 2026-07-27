"""
execution_compliance_engine.py

Sprint 39.3

Institutional Execution Compliance Engine

Evaluates immutable execution event streams against
institutional trading policies.

Unlike ExecutionEventStreamValidator, which verifies the
integrity of the event stream, this engine verifies whether
the execution complied with configurable business and
risk policies.

Execution Events
        ↓
ExecutionEventReplayer
        ↓
ExecutionComplianceEngine
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .execution_event_replayer import (
    ExecutionEventReplayer,
    get_execution_event_replayer,
)


# ==============================================================================
# Compliance Result
# ==============================================================================


@dataclass
class ComplianceResult:

    compliant: bool = True

    score: int = 100

    checks_run: int = 0

    violations: List[str] = field(default_factory=list)

    warnings: List[str] = field(default_factory=list)

    details: Dict[str, Any] = field(default_factory=dict)

    def fail(self, message: str):

        self.compliant = False

        self.violations.append(message)

    def warn(self, message: str):

        self.warnings.append(message)

    def to_dict(self):

        return {

            "compliant": self.compliant,

            "score": self.score,

            "checks_run": self.checks_run,

            "violations": self.violations,

            "warnings": self.warnings,

            "details": self.details,

        }


# ==============================================================================
# Compliance Engine
# ==============================================================================


class ExecutionComplianceEngine:

    DEFAULT_POLICY = {

        #
        # Order
        #

        "max_order_units": 10_000_000,

        "min_order_units": 1,

        "allowed_order_types": {

            "MARKET",

            "LIMIT",

            "STOP",

            "STOP_LIMIT",

        },

        #
        # Position
        #

        "max_position_units": 25_000_000,

        "max_leverage": 50,

        #
        # Risk
        #

        "require_stop_loss": False,

        "require_take_profit": False,

        "max_drawdown_pct": 25,

        "max_margin_utilization": 95,

        #
        # Portfolio
        #

        "max_open_positions": 100,

        "max_open_orders": 250,

    }

    def __init__(

        self,

        *,

        db,

        replayer: Optional[
            ExecutionEventReplayer
        ] = None,

        policy: Optional[
            Dict[str, Any]
        ] = None,

    ):

        self.db = db

        self.replayer = (
            replayer
            or get_execution_event_replayer(
                db=db,
            )
        )

        self.policy = dict(
            self.DEFAULT_POLICY
        )

        if policy:

            self.policy.update(
                policy
            )

    # ==============================================================
    # Public API
    # ==============================================================

    def evaluate_execution(

        self,

        *,

        execution_id: str,

    ) -> ComplianceResult:

        events = self.replayer.load_events(

            execution_id=execution_id,

        )

        return self.evaluate_events(
            events=events,
        )

    # --------------------------------------------------------------

    def evaluate_order(

        self,

        *,

        broker_order_id: str,

    ) -> ComplianceResult:

        events = self.replayer.load_events(

            broker_order_id=broker_order_id,

        )

        return self.evaluate_events(
            events=events,
        )

    # --------------------------------------------------------------

    def evaluate_position(

        self,

        *,

        position_id: str,

    ) -> ComplianceResult:

        events = self.replayer.load_events(

            position_id=position_id,

        )

        return self.evaluate_events(
            events=events,
        )

    # --------------------------------------------------------------

    def evaluate_account(

        self,

        *,

        account_id: str,

    ) -> ComplianceResult:

        events = self.replayer.load_events(

            account_id=account_id,

        )

        return self.evaluate_events(
            events=events,
        )

    # --------------------------------------------------------------

    def evaluate_portfolio(

        self,

        *,

        portfolio_id: str,

    ) -> ComplianceResult:

        events = self.replayer.load_events(

            portfolio_id=portfolio_id,

        )

        return self.evaluate_events(
            events=events,
        )

    # --------------------------------------------------------------

    def evaluate_events(

        self,

        *,

        events: List[Dict[str, Any]],

    ) -> ComplianceResult:

        result = ComplianceResult()

        self._check_order_rules(
            events,
            result,
        )

        self._check_position_rules(
            events,
            result,
        )

        self._check_risk_rules(
            events,
            result,
        )

        self._check_account_rules(
            events,
            result,
        )

        self._check_portfolio_rules(
            events,
            result,
        )

        self._score(
            result,
        )

        return result

    # ==============================================================
    # Report
    # ==============================================================

    def build_report(

        self,

        *,

        events,

        entity_type,

        entity_id,

    ) -> Dict[str, Any]:

        result = self.evaluate_events(
            events=events,
        )

        report = result.to_dict()

        report.update({

            "entity_type": entity_type,

            "entity_id": entity_id,

        })

        return report

    # ==============================================================
    # Order Rules
    # ==============================================================

    def _check_order_rules(

        self,

        events,

        result,

    ):

        for event in events:

            result.checks_run += 1

            units = event.get("units") or 0

            order_type = (
                event.get("order_type")
                or ""
            ).upper()

            if (
                units
                < self.policy[
                    "min_order_units"
                ]
            ):

                result.fail(
                    "Order below minimum size."
                )

            if (
                units
                > self.policy[
                    "max_order_units"
                ]
            ):

                result.fail(
                    "Order exceeds maximum size."
                )

            if (
                order_type
                and order_type
                not in self.policy[
                    "allowed_order_types"
                ]
            ):

                result.fail(
                    f"Unsupported order type: {order_type}"
                )

    # ==============================================================
    # Position Rules
    # ==============================================================

    def _check_position_rules(

        self,

        events,

        result,

    ):

        for event in events:

            result.checks_run += 1

            units = (
                event.get("units")
                or 0
            )

            leverage = (
                event.get("leverage")
                or 1
            )

            if (
                units
                > self.policy[
                    "max_position_units"
                ]
            ):

                result.fail(
                    "Position exceeds maximum size."
                )

            if (
                leverage
                > self.policy[
                    "max_leverage"
                ]
            ):

                result.fail(
                    "Leverage exceeds policy."
                )

    # ==============================================================
    # Risk Rules
    # ==============================================================

    def _check_risk_rules(

        self,

        events,

        result,

    ):

        for event in events:

            result.checks_run += 1

            if (

                self.policy[
                    "require_stop_loss"
                ]

                and

                event.get("stop_price")
                is None

            ):

                result.warn(
                    "Missing stop loss."
                )

            if (

                self.policy[
                    "require_take_profit"
                ]

                and

                event.get(
                    "target_price"
                ) is None

            ):

                result.warn(
                    "Missing take profit."
                )

    # ==============================================================
    # Account Rules
    # ==============================================================

    def _check_account_rules(

        self,

        events,

        result,

    ):

        for event in events:

            result.checks_run += 1

            utilization = (
                event.get(
                    "margin_utilization"
                )
                or 0
            )

            if (
                utilization
                > self.policy[
                    "max_margin_utilization"
                ]
            ):

                result.fail(
                    "Margin utilization exceeded."
                )

    # ==============================================================
    # Portfolio Rules
    # ==============================================================

    def _check_portfolio_rules(

        self,

        events,

        result,

    ):

        max_positions = 0

        max_orders = 0

        current_positions = 0

        current_orders = 0

        for event in events:

            result.checks_run += 1

            t = event.get(
                "event_type"
            )

            if t == "POSITION_OPENED":
                current_positions += 1

            elif t == "POSITION_CLOSED":
                current_positions = max(
                    0,
                    current_positions - 1,
                )

            elif t == "NEW_ORDER":
                current_orders += 1

            elif t in {
                "ORDER_FILLED",
                "ORDER_CANCELLED",
                "ORDER_REJECTED",
                "ORDER_EXPIRED",
            }:
                current_orders = max(
                    0,
                    current_orders - 1,
                )

            max_positions = max(
                max_positions,
                current_positions,
            )

            max_orders = max(
                max_orders,
                current_orders,
            )

        if (
            max_positions
            > self.policy[
                "max_open_positions"
            ]
        ):

            result.fail(
                "Too many open positions."
            )

        if (
            max_orders
            > self.policy[
                "max_open_orders"
            ]
        ):

            result.fail(
                "Too many open orders."
            )

        result.details[
            "peak_open_positions"
        ] = max_positions

        result.details[
            "peak_open_orders"
        ] = max_orders

    # ==============================================================
    # Score
    # ==============================================================

    def _score(

        self,

        result,

    ):

        penalty = (

            len(result.violations) * 10

            +

            len(result.warnings) * 2

        )

        result.score = max(
            0,
            100 - penalty,
        )

        result.compliant = (
            len(result.violations)
            == 0
        )


# ==============================================================================
# Factory
# ==============================================================================

_COMPLIANCE_ENGINE = None


def get_execution_compliance_engine(

    *,

    db,

    cache: bool = True,

) -> ExecutionComplianceEngine:

    global _COMPLIANCE_ENGINE

    if (

        not cache

        or _COMPLIANCE_ENGINE is None

    ):

        _COMPLIANCE_ENGINE = (
            ExecutionComplianceEngine(
                db=db,
            )
        )

    return _COMPLIANCE_ENGINE