"""
==============================================================================
forex_partial_profit_manager.py

Sprint FX-4
Institutional Partial Profit Manager

This manager is responsible for automatically scaling out of winning
positions using configurable institutional exit rules.

Architecture

ForexTradeManagementEngine
            │
            ▼
ForexPartialProfitManager
            │
            ▼
ForexPositionManagementEngine
            │
            ▼
Execution Service
            │
            ▼
Execution Framework

The manager NEVER:

    • Executes trades directly
    • Updates SQL tables
    • Modifies repositories
    • Changes position objects directly

Every modification flows through:

    ForexPositionManagementEngine.close_partial_position()

which produces immutable execution events.

Supported Strategies

    • Fixed Risk/Reward Targets
    • Percentage Profit Targets
    • ATR Targets
    • Volatility Targets
    • AI Targets (future)

==============================================================================

"""

from __future__ import annotations

import logging

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from modules.execution.execution_context import ExecutionContext

from modules.forex.forex_position_management_engine import (
    ForexPositionManagementEngine,
    get_forex_position_management_engine,
)

logger = logging.getLogger(__name__)

# ==============================================================================
# Exit Strategy Types
# ==============================================================================


class PartialProfitMethod(str, Enum):

    R_MULTIPLE = "R_MULTIPLE"

    FIXED_PERCENT = "FIXED_PERCENT"

    ATR = "ATR"

    VOLATILITY = "VOLATILITY"

    AI = "AI"


# ==============================================================================
# Exit Stage Definitions
# ==============================================================================


class PartialProfitStage(str, Enum):

    NONE = "NONE"

    FIRST = "FIRST"

    SECOND = "SECOND"

    THIRD = "THIRD"

    FINAL = "FINAL"


# ==============================================================================
# Configuration
# ==============================================================================


@dataclass
class PartialProfitConfig:
    """
    Institutional partial-profit configuration.
    """

    enabled: bool = True

    #
    # Strategy selection
    #
    method: PartialProfitMethod = PartialProfitMethod.R_MULTIPLE

    #
    # First scale-out
    #
    first_target_rr: float = 1.0

    first_target_percent: float = 0.25

    #
    # Second scale-out
    #
    second_target_rr: float = 2.0

    second_target_percent: float = 0.25

    #
    # Third scale-out
    #
    third_target_rr: float = 3.0

    third_target_percent: float = 0.25

    #
    # Remaining position
    #
    final_target_rr: float = 4.0

    #
    # Never exceed original quantity
    #
    prevent_over_close: bool = True

    #
    # Skip stages already completed
    #
    skip_completed_stages: bool = True

    #
    # Enable runtime diagnostics
    #
    diagnostics: bool = False

    #
    # Allow AI override (future)
    #
    allow_ai_override: bool = False

    #
    # Require positive unrealized PnL
    #
    require_profit: bool = True

# ==============================================================================
# Partial Profit Models
# ==============================================================================


@dataclass
class PartialProfitTarget:
    """
    Defines one institutional scale-out target.

    Example

        Stage 1

            1R

            Sell 25%

        Stage 2

            2R

            Sell 25%

        Stage 3

            3R

            Sell 25%

        Final

            4R

            Sell remainder
    """

    stage: PartialProfitStage

    risk_multiple: float

    quantity_percent: float

    enabled: bool = True

    description: str = ""


# ------------------------------------------------------------------------------


@dataclass
class PartialProfitDecision:
    """
    Decision returned by the manager
    before any execution occurs.
    """

    execute: bool = False

    stage: PartialProfitStage = PartialProfitStage.NONE

    quantity: float = 0.0

    quantity_percent: float = 0.0

    target_price: float = 0.0

    achieved_rr: float = 0.0

    message: str = ""

    metadata: Optional[
        Dict[str, Any]
    ] = None

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return {

            "execute":
                self.execute,

            "stage":
                self.stage.value,

            "quantity":
                self.quantity,

            "quantity_percent":
                self.quantity_percent,

            "target_price":
                self.target_price,

            "achieved_rr":
                self.achieved_rr,

            "message":
                self.message,

            "metadata":
                self.metadata or {},

        }


# ==============================================================================
# Runtime State
# ==============================================================================


@dataclass
class PartialProfitState:
    """
    Runtime state attached to a position.

    This object tracks completed
    scale-out stages.
    """

    completed_stages: List[
        PartialProfitStage
    ]

    remaining_quantity: float

    original_quantity: float

    last_stage: PartialProfitStage = (
        PartialProfitStage.NONE
    )

    last_execution: Optional[
        datetime
    ] = None

    execution_count: int = 0

    def completed(
        self,
        stage: PartialProfitStage,
    ) -> bool:

        return stage in self.completed_stages

    def mark_completed(
        self,
        stage: PartialProfitStage,
    ) -> None:

        if stage not in self.completed_stages:

            self.completed_stages.append(
                stage,
            )

        self.last_stage = stage

        self.execution_count += 1

        self.last_execution = datetime.utcnow()


# ==============================================================================
# Helper Utilities
# ==============================================================================


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:

    try:

        if value is None:

            return default

        return float(value)

    except Exception:

        return default


# ------------------------------------------------------------------------------


def _clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:

    return max(

        minimum,

        min(

            value,

            maximum,

        ),

    )


# ------------------------------------------------------------------------------


def _round_quantity(
    quantity: float,
    precision: int = 2,
) -> float:

    return round(

        quantity,

        precision,

    )


# ------------------------------------------------------------------------------


def _utc_now(
) -> datetime:

    return datetime.utcnow()


# ==============================================================================
# Default Institutional Targets
# ==============================================================================


DEFAULT_TARGETS: List[
    PartialProfitTarget
] = [

    PartialProfitTarget(

        stage=PartialProfitStage.FIRST,

        risk_multiple=1.0,

        quantity_percent=0.25,

        description="Scale out first 25% at 1R",

    ),

    PartialProfitTarget(

        stage=PartialProfitStage.SECOND,

        risk_multiple=2.0,

        quantity_percent=0.25,

        description="Scale out second 25% at 2R",

    ),

    PartialProfitTarget(

        stage=PartialProfitStage.THIRD,

        risk_multiple=3.0,

        quantity_percent=0.25,

        description="Scale out third 25% at 3R",

    ),

    PartialProfitTarget(

        stage=PartialProfitStage.FINAL,

        risk_multiple=4.0,

        quantity_percent=1.00,

        description="Close remaining position",

    ),

]
# ==============================================================================
# Partial Profit Manager
# ==============================================================================


class ForexPartialProfitManager:
    """
    Institutional Partial Profit Manager.

    Responsibilities

        • Evaluate profit milestones

        • Determine the next scale-out stage

        • Calculate quantity to exit

        • Delegate execution through the
          ForexPositionManagementEngine

        • Never modify positions directly
    """

    def __init__(
        self,
        *,
        db,
        portfolio_engine=None,
        config: Optional[
            PartialProfitConfig
        ] = None,
    ):

        self.db = db

        self.config = config or PartialProfitConfig()

        #
        # Position Management
        #

        self.position_manager: ForexPositionManagementEngine = (

            get_forex_position_management_engine(

                db=db,

                portfolio_engine=portfolio_engine,

                actor="partial_profit_manager",

                source="FOREX",

            )

        )

        #
        # Institutional target ladder
        #

        self.targets: List[
            PartialProfitTarget
        ] = list(DEFAULT_TARGETS)

        #
        # Runtime metrics
        #

        self.reset_metrics()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def enabled(
        self,
    ) -> bool:

        return bool(

            self.config.enabled

        )

    # ------------------------------------------------------------------
    # Position Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def value(
        position: Any,
        key: str,
        default=None,
    ):

        if isinstance(position, dict):

            return position.get(

                key,

                default,

            )

        return getattr(

            position,

            key,

            default,

        )

    # ------------------------------------------------------------------

    @classmethod
    def position_id(
        cls,
        position: Any,
    ) -> Optional[str]:

        return (

            cls.value(

                position,

                "position_id",

            )

            or

            cls.value(

                position,

                "id",

            )

        )

    # ------------------------------------------------------------------

    @classmethod
    def pair(
        cls,
        position: Any,
    ) -> str:

        return (

            cls.value(

                position,

                "pair",

            )

            or

            cls.value(

                position,

                "symbol",

                "",

            )

        )

    # ------------------------------------------------------------------

    @classmethod
    def side(
        cls,
        position: Any,
    ) -> str:

        return str(

            cls.value(

                position,

                "side",

                "",

            )

        ).upper()

    # ------------------------------------------------------------------

    @classmethod
    def quantity(
        cls,
        position: Any,
    ) -> float:

        return _safe_float(

            cls.value(

                position,

                "quantity",

                cls.value(

                    position,

                    "qty",

                    0.0,

                ),

            )

        )

    # ------------------------------------------------------------------

    @classmethod
    def remaining_quantity(
        cls,
        position: Any,
    ) -> float:

        return _safe_float(

            cls.value(

                position,

                "remaining_quantity",

                cls.quantity(position),

            )

        )

    # ------------------------------------------------------------------

    @classmethod
    def entry_price(
        cls,
        position: Any,
    ) -> float:

        return _safe_float(

            cls.value(

                position,

                "avg_entry_price",

                cls.value(

                    position,

                    "entry_price",

                    0.0,

                ),

            )

        )

    # ------------------------------------------------------------------

    @classmethod
    def current_price(
        cls,
        position: Any,
    ) -> float:

        return _safe_float(

            cls.value(

                position,

                "current_price",

                0.0,

            )

        )

    # ------------------------------------------------------------------

    @classmethod
    def stop_price(
        cls,
        position: Any,
    ) -> Optional[float]:

        stop = cls.value(

            position,

            "stop_price",

        )

        if stop is None:

            return None

        return _safe_float(

            stop,

        )

    # ------------------------------------------------------------------

    @classmethod
    def risk_per_unit(
        cls,
        position: Any,
    ) -> float:
        """
        Risk per unit.

        Used to calculate achieved R.
        """

        entry = cls.entry_price(position)

        stop = cls.stop_price(position)

        if stop is None:

            return 0.0

        return abs(

            entry - stop

        )

    # ------------------------------------------------------------------

    @classmethod
    def current_r_multiple(
        cls,
        position: Any,
    ) -> float:
        """
        Current achieved R multiple.
        """

        risk = cls.risk_per_unit(

            position,

        )

        if risk <= 0:

            return 0.0

        entry = cls.entry_price(

            position,

        )

        current = cls.current_price(

            position,

        )

        side = cls.side(

            position,

        )

        if side in {

            "BUY",

            "LONG",

        }:

            profit = current - entry

        else:

            profit = entry - current

        return profit / risk

    # ------------------------------------------------------------------

    @classmethod
    def state(
        cls,
        position: Any,
    ) -> PartialProfitState:
        """
        Build runtime state from a position.

        This currently reconstructs the state from
        persisted position fields. Later phases can
        replace this with repository-backed state.
        """

        completed = cls.value(

            position,

            "completed_partial_stages",

            [],

        )

        stages: List[
            PartialProfitStage
        ] = []

        for stage in completed:

            try:

                stages.append(

                    PartialProfitStage(stage)

                )

            except Exception:

                pass

        return PartialProfitState(

            completed_stages=stages,

            remaining_quantity=cls.remaining_quantity(
                position,
            ),

            original_quantity=cls.quantity(
                position,
            ),

            execution_count=len(stages),

        )

    # ------------------------------------------------------------------
    # Runtime Metrics
    # ------------------------------------------------------------------

    def reset_metrics(
        self,
    ) -> None:

        self._metrics = {

            "positions_evaluated": 0,

            "partial_exits": 0,

            "stage1": 0,

            "stage2": 0,

            "stage3": 0,

            "final": 0,

            "positions_skipped": 0,

            "errors": 0,

            "last_run": None,

            "last_duration_ms": 0.0,

        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Eligibility
    # ------------------------------------------------------------------

    def eligible(
            self,
            position: Dict[str, Any],
    ) -> bool:
        """
        Determine whether a position can be evaluated for a
        staged partial-profit exit.
        """

        if not self.enabled():
            return False

        position_id = self.position_id(position)

        if not position_id:
            return False

        status = str(
            self.value(
                position,
                "status",
                "",
            )
        ).upper()

        if status and status not in {
            "OPEN",
            "ACTIVE",
            "LIVE",
            "FILLED",
            "PARTIALLY_CLOSED",
        }:
            return False

        side = self.side(position)

        if side not in {
            "BUY",
            "LONG",
            "SELL",
            "SHORT",
        }:
            return False

        original_quantity = self.quantity(position)
        remaining_quantity = self.remaining_quantity(position)

        if original_quantity <= 0 or remaining_quantity <= 0:
            return False

        entry = self.entry_price(position)
        current = self.current_price(position)

        if entry <= 0 or current <= 0:
            return False

        if self.config.require_profit:

            if side in {"BUY", "LONG"} and current <= entry:
                return False

            if side in {"SELL", "SHORT"} and current >= entry:
                return False

        if (
                self.config.method
                == PartialProfitMethod.R_MULTIPLE
                and self.risk_per_unit(position) <= 0
        ):
            return False

        return self.next_target(position) is not None

    # ------------------------------------------------------------------
    # Configured Target Ladder
    # ------------------------------------------------------------------

    def configured_targets(
            self,
    ) -> List[PartialProfitTarget]:
        """
        Build the active target ladder from runtime configuration.

        This ensures configuration changes are reflected immediately
        instead of relying only on the static DEFAULT_TARGETS list.
        """

        return [

            PartialProfitTarget(
                stage=PartialProfitStage.FIRST,
                risk_multiple=self.config.first_target_rr,
                quantity_percent=self.config.first_target_percent,
                enabled=(
                        self.config.first_target_rr > 0
                        and self.config.first_target_percent > 0
                ),
                description=(
                    f"Scale out "
                    f"{self.config.first_target_percent:.0%} "
                    f"at {self.config.first_target_rr:.2f}R"
                ),
            ),

            PartialProfitTarget(
                stage=PartialProfitStage.SECOND,
                risk_multiple=self.config.second_target_rr,
                quantity_percent=self.config.second_target_percent,
                enabled=(
                        self.config.second_target_rr > 0
                        and self.config.second_target_percent > 0
                ),
                description=(
                    f"Scale out "
                    f"{self.config.second_target_percent:.0%} "
                    f"at {self.config.second_target_rr:.2f}R"
                ),
            ),

            PartialProfitTarget(
                stage=PartialProfitStage.THIRD,
                risk_multiple=self.config.third_target_rr,
                quantity_percent=self.config.third_target_percent,
                enabled=(
                        self.config.third_target_rr > 0
                        and self.config.third_target_percent > 0
                ),
                description=(
                    f"Scale out "
                    f"{self.config.third_target_percent:.0%} "
                    f"at {self.config.third_target_rr:.2f}R"
                ),
            ),

            PartialProfitTarget(
                stage=PartialProfitStage.FINAL,
                risk_multiple=self.config.final_target_rr,
                quantity_percent=1.0,
                enabled=self.config.final_target_rr > 0,
                description=(
                    f"Close remaining position at "
                    f"{self.config.final_target_rr:.2f}R"
                ),
            ),

        ]

    # ------------------------------------------------------------------
    # Next Target
    # ------------------------------------------------------------------

    def next_target(
            self,
            position: Dict[str, Any],
    ) -> Optional[PartialProfitTarget]:
        """
        Return the next enabled, uncompleted target stage.

        Stages are processed in order:

            FIRST
            SECOND
            THIRD
            FINAL
        """

        state = self.state(position)

        for target in self.configured_targets():

            if not target.enabled:
                continue

            if (
                    self.config.skip_completed_stages
                    and state.completed(target.stage)
            ):
                continue

            return target

        return None

    # ------------------------------------------------------------------
    # Target Price
    # ------------------------------------------------------------------

    def calculate_target_price(
            self,
            position: Dict[str, Any],
            target: PartialProfitTarget,
    ) -> float:
        """
        Calculate the price corresponding to a target stage.

        For R-multiple mode:

            risk distance = abs(entry - initial stop)

            BUY/LONG:
                target = entry + risk distance * R

            SELL/SHORT:
                target = entry - risk distance * R
        """

        entry = self.entry_price(position)
        side = self.side(position)

        if entry <= 0:
            return 0.0

        if self.config.method == PartialProfitMethod.R_MULTIPLE:

            risk = self.risk_per_unit(position)

            if risk <= 0:
                return 0.0

            distance = risk * target.risk_multiple

            if side in {"BUY", "LONG"}:
                price = entry + distance
            else:
                price = entry - distance

            return round(price, 5)

        if self.config.method == PartialProfitMethod.FIXED_PERCENT:

            percentage = target.risk_multiple / 100.0

            if side in {"BUY", "LONG"}:
                price = entry * (1.0 + percentage)
            else:
                price = entry * (1.0 - percentage)

            return round(price, 5)

        if self.config.method == PartialProfitMethod.ATR:

            atr = _safe_float(
                self.value(
                    position,
                    "atr",
                    self.value(
                        position,
                        "atr_14",
                        0.0,
                    ),
                )
            )

            if atr <= 0:
                return 0.0

            distance = atr * target.risk_multiple

            if side in {"BUY", "LONG"}:
                price = entry + distance
            else:
                price = entry - distance

            return round(price, 5)

        if self.config.method == PartialProfitMethod.VOLATILITY:

            volatility = _safe_float(
                self.value(
                    position,
                    "volatility",
                    self.value(
                        position,
                        "realized_volatility",
                        0.0,
                    ),
                )
            )

            if volatility <= 0:
                return 0.0

            distance = volatility * target.risk_multiple

            if side in {"BUY", "LONG"}:
                price = entry + distance
            else:
                price = entry - distance

            return round(price, 5)

        #
        # AI mode requires an externally supplied target.
        #

        if self.config.method == PartialProfitMethod.AI:
            ai_target = _safe_float(
                self.value(
                    position,
                    "ai_partial_profit_target",
                    0.0,
                )
            )

            return round(ai_target, 5) if ai_target > 0 else 0.0

        return 0.0

    # ------------------------------------------------------------------
    # Target Reached
    # ------------------------------------------------------------------

    def target_reached(
            self,
            position: Dict[str, Any],
            target: PartialProfitTarget,
    ) -> bool:
        """
        Determine whether the current market price has reached the
        supplied partial-profit target.
        """

        current = self.current_price(position)

        if current <= 0:
            return False

        target_price = self.calculate_target_price(
            position,
            target,
        )

        if target_price <= 0:
            return False

        side = self.side(position)

        if side in {"BUY", "LONG"}:
            return current >= target_price

        return current <= target_price

    # ------------------------------------------------------------------
    # Achieved R
    # ------------------------------------------------------------------

    def achieved_r_multiple(
            self,
            position: Dict[str, Any],
    ) -> float:
        """
        Return the current achieved risk multiple.
        """

        return self.current_r_multiple(position)

    # ------------------------------------------------------------------
    # Quantity Calculation
    # ------------------------------------------------------------------

    def calculate_stage_quantity(
            self,
            position: Dict[str, Any],
            target: PartialProfitTarget,
    ) -> float:
        """
        Calculate the quantity to close for a staged exit.

        Non-final stages use the original position quantity so each
        configured percentage represents the original trade size.

        The final stage closes the entire remaining quantity.
        """

        state = self.state(position)

        remaining = max(
            state.remaining_quantity,
            0.0,
        )

        if remaining <= 0:
            return 0.0

        if target.stage == PartialProfitStage.FINAL:
            return _round_quantity(
                remaining,
            )

        percentage = _clamp(
            target.quantity_percent,
            0.0,
            1.0,
        )

        quantity = (
                state.original_quantity
                * percentage
        )

        if self.config.prevent_over_close:
            quantity = min(
                quantity,
                remaining,
            )

        return _round_quantity(
            max(quantity, 0.0),
        )

    # ------------------------------------------------------------------
    # Target Diagnostics
    # ------------------------------------------------------------------

    def target_summary(
            self,
            position: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Return the full target ladder and current completion state.
        """

        state = self.state(position)
        current = self.current_price(position)

        rows: List[Dict[str, Any]] = []

        for target in self.configured_targets():
            target_price = self.calculate_target_price(
                position,
                target,
            )

            rows.append(
                {
                    "stage": target.stage.value,
                    "enabled": target.enabled,
                    "completed": state.completed(target.stage),
                    "risk_multiple": target.risk_multiple,
                    "quantity_percent": target.quantity_percent,
                    "target_price": target_price,
                    "current_price": current,
                    "reached": (
                        self.target_reached(position, target)
                        if target.enabled
                        else False
                    ),
                    "description": target.description,
                }
            )

        return rows

    # ------------------------------------------------------------------
    # Eligibility Diagnostics
    # ------------------------------------------------------------------

    def explain_eligibility(
            self,
            position: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Explain why a position is or is not eligible.
        """

        next_target = self.next_target(position)
        state = self.state(position)

        return {

            "manager":
                "ForexPartialProfitManager",

            "enabled":
                self.enabled(),

            "position_id":
                self.position_id(position),

            "pair":
                self.pair(position),

            "side":
                self.side(position),

            "entry_price":
                self.entry_price(position),

            "current_price":
                self.current_price(position),

            "stop_price":
                self.stop_price(position),

            "original_quantity":
                state.original_quantity,

            "remaining_quantity":
                state.remaining_quantity,

            "current_r_multiple":
                round(
                    self.current_r_multiple(position),
                    4,
                ),

            "completed_stages": [
                stage.value
                for stage in state.completed_stages
            ],

            "next_stage":
                (
                    next_target.stage.value
                    if next_target
                    else None
                ),

            "next_target_price":
                (
                    self.calculate_target_price(
                        position,
                        next_target,
                    )
                    if next_target
                    else None
                ),

            "target_reached":
                (
                    self.target_reached(
                        position,
                        next_target,
                    )
                    if next_target
                    else False
                ),

            "eligible":
                self.eligible(position),

        }

    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Partial Exit Decision
    # ------------------------------------------------------------------

    def calculate_partial_exit(
            self,
            position: Dict[str, Any],
    ) -> PartialProfitDecision:
        """
        Determine whether a staged partial exit should occur.

        This method DOES NOT execute any trades.

        It simply returns a PartialProfitDecision that will
        later be executed by manage_position().
        """

        #
        # Default decision
        #

        decision = PartialProfitDecision(

            execute=False,

            stage=PartialProfitStage.NONE,

            message="No partial profit action.",

        )

        #
        # Eligibility
        #

        if not self.eligible(position):
            decision.message = (

                "Position is not eligible."

            )

            return decision

        #
        # Next target
        #

        target = self.next_target(position)

        if target is None:
            decision.message = (

                "No remaining targets."

            )

            return decision

        #
        # Has target been reached?
        #

        if not self.target_reached(

                position,

                target,

        ):
            decision.stage = target.stage

            decision.target_price = (

                self.calculate_target_price(

                    position,

                    target,

                )

            )

            decision.achieved_rr = (

                self.achieved_r_multiple(

                    position,

                )

            )

            decision.message = (

                "Target not yet reached."

            )

            return decision

        #
        # Calculate quantity
        #

        quantity = self.calculate_stage_quantity(

            position,

            target,

        )

        if quantity <= 0:
            decision.stage = target.stage

            decision.message = (

                "Calculated quantity is zero."

            )

            return decision

        #
        # Build execution decision
        #

        decision.execute = True

        decision.stage = target.stage

        decision.quantity = quantity

        decision.quantity_percent = (

            target.quantity_percent

        )

        decision.target_price = (

            self.calculate_target_price(

                position,

                target,

            )

        )

        decision.achieved_rr = (

            self.achieved_r_multiple(

                position,

            )

        )

        decision.message = (

            f"{target.stage.value} "

            f"partial-profit target reached."

        )

        decision.metadata = {

            "method":

                self.config.method.value,

            "pair":

                self.pair(position),

            "side":

                self.side(position),

            "entry_price":

                self.entry_price(position),

            "current_price":

                self.current_price(position),

            "remaining_quantity":

                self.remaining_quantity(position),

            "risk_multiple":

                target.risk_multiple,

            "description":

                target.description,

        }

        return decision

    # ------------------------------------------------------------------
    # Decision Helpers
    # ------------------------------------------------------------------

    def should_execute(
            self,
            decision: PartialProfitDecision,
    ) -> bool:
        """
        Convenience wrapper.
        """

        return bool(

            decision.execute

        )

    # ------------------------------------------------------------------

    def next_stage(
            self,
            position: Dict[str, Any],
    ) -> PartialProfitStage:
        """
        Return the next stage only.
        """

        target = self.next_target(

            position,

        )

        if target is None:
            return PartialProfitStage.NONE

        return target.stage

    # ------------------------------------------------------------------

    def target_completed(
            self,
            position: Dict[str, Any],
            stage: PartialProfitStage,
    ) -> bool:
        """
        Has this stage already been completed?
        """

        return self.state(

            position,

        ).completed(stage)

    # ------------------------------------------------------------------

    def remaining_position_pct(
            self,
            position: Dict[str, Any],
    ) -> float:
        """
        Remaining position as a percentage
        of the original position.
        """

        state = self.state(

            position,

        )

        if state.original_quantity <= 0:
            return 0.0

        return (

                state.remaining_quantity

                /

                state.original_quantity

        )

    # ------------------------------------------------------------------

    def decision_summary(
            self,
            position: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Dashboard-friendly summary of the
        current partial-profit decision.
        """

        decision = self.calculate_partial_exit(

            position,

        )

        return {

            "execute":

                decision.execute,

            "stage":

                decision.stage.value,

            "quantity":

                decision.quantity,

            "quantity_percent":

                decision.quantity_percent,

            "target_price":

                decision.target_price,

            "achieved_rr":

                round(

                    decision.achieved_rr,

                    2,

                ),

            "remaining_position_pct":

                round(

                    self.remaining_position_pct(

                        position,

                    )

                    * 100,

                    2,

                ),

            "message":

                decision.message,

        }

    # ------------------------------------------------------------------

    def manage_position(
            self,
            position: Dict[str, Any],
    ) -> Optional[ExecutionContext]:
        """
        Execute a partial exit for a single position.

        Implemented in Part 3.
        """
        raise NotImplementedError()

    # ------------------------------------------------------------------

    def manage_positions(
            self,
            positions: List[Dict[str, Any]],
    ) -> List[ExecutionContext]:
        """
        Batch execution.

        Implemented in Part 3.
        """
        raise NotImplementedError()

    # ------------------------------------------------------------------

    def manage_account(
            self,
            *,
            account_id: str,
    ) -> List[ExecutionContext]:
        """
        Account processing.

        Implemented in Part 3.
        """
        raise NotImplementedError()

    # ------------------------------------------------------------------

    def manage_portfolio(
            self,
            *,
            portfolio_id: str,
    ) -> List[ExecutionContext]:
        """
        Portfolio processing.

        Implemented in Part 3.
        """
        raise NotImplementedError()

    # ------------------------------------------------------------------

    def dry_run(
            self,
            position: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Simulate the next partial exit.

        Implemented in Part 4.
        """
        raise NotImplementedError()

    # ------------------------------------------------------------------

    def process(
            self,
            *,
            account_id: Optional[str] = None,
            portfolio_id: Optional[str] = None,
    ) -> List[ExecutionContext]:
        """
        Primary orchestration entry point.

        Implemented in Part 4.
        """
        raise NotImplementedError()

    # ------------------------------------------------------------------

    def statistics(
            self,
    ) -> Dict[str, Any]:
        """
        Runtime statistics.

        Implemented in Part 4.
        """
        raise NotImplementedError()

    # ------------------------------------------------------------------

    def metrics(
            self,
    ) -> Dict[str, Any]:
        """
        Runtime metrics.

        Implemented in Part 4.
        """
        raise NotImplementedError()

    # ------------------------------------------------------------------

    def health(
            self,
    ) -> Dict[str, Any]:
        """
        Operations dashboard health.

        Implemented in Part 4.
        """
        raise NotImplementedError()

    # ------------------------------------------------------------------

    def validate_configuration(
            self,
    ) -> List[str]:
        """
        Validate runtime configuration.

        Implemented in Part 4.
        """
        raise NotImplementedError()

    # ------------------------------------------------------------------

    def update_configuration(
            self,
            **kwargs,
    ) -> None:
        """
        Update runtime configuration.

        Implemented in Part 4.
        """
        raise NotImplementedError()

    # ------------------------------------------------------------------

    def __repr__(
            self,
    ) -> str:
        return (

            f"ForexPartialProfitManager("

            f"enabled={self.config.enabled}, "

            f"method={self.config.method.value})"

        )

    # ------------------------------------------------------------------
    # Decision Validation
    # ------------------------------------------------------------------

    def validate_decision(
            self,
            position: Dict[str, Any],
            decision: PartialProfitDecision,
    ) -> List[str]:
        """
        Validate a calculated decision before execution.
        """

        warnings: List[str] = []

        if not decision.execute:
            return warnings

        remaining = self.remaining_quantity(position)

        if decision.quantity <= 0:
            warnings.append(
                "Execution quantity must be greater than zero."
            )

        if decision.quantity > remaining:
            warnings.append(
                "Execution quantity exceeds remaining position."
            )

        if decision.target_price <= 0:
            warnings.append(
                "Target price is invalid."
            )

        if decision.stage == PartialProfitStage.NONE:
            warnings.append(
                "No stage selected."
            )

        return warnings

    # ------------------------------------------------------------------
    # Stage Progress
    # ------------------------------------------------------------------

    def progress(
            self,
            position: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Return stage progress information.
        """

        state = self.state(position)

        completed = len(state.completed_stages)

        total = len(self.configured_targets())

        percent = (
            completed / total
            if total > 0
            else 0.0
        )

        return {

            "completed_stages": completed,

            "total_stages": total,

            "progress_percent": round(
                percent * 100,
                2,
            ),

            "remaining_quantity":
                state.remaining_quantity,

            "original_quantity":
                state.original_quantity,

            "execution_count":
                state.execution_count,

            "last_stage":
                state.last_stage.value,

        }

    # ------------------------------------------------------------------
    # Explain
    # ------------------------------------------------------------------

    def explain(
            self,
            position: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Full diagnostic report.
        """

        decision = self.calculate_partial_exit(
            position,
        )

        validation = self.validate_decision(
            position,
            decision,
        )

        return {

            "manager":
                "ForexPartialProfitManager",

            "eligible":
                self.eligible(position),

            "decision":
                decision.to_dict(),

            "validation":
                validation,

            "progress":
                self.progress(position),

            "targets":
                self.target_summary(position),

        }

    # ------------------------------------------------------------------
    # Next Action
    # ------------------------------------------------------------------

    def next_action(
            self,
            position: Dict[str, Any],
    ) -> str:
        """
        Human-readable next action.
        """

        decision = self.calculate_partial_exit(
            position,
        )

        if decision.execute:
            return (

                f"Execute "

                f"{decision.stage.value} "

                f"partial exit."

            )

        target = self.next_target(position)

        if target is None:
            return "All stages completed."

        return (

            f"Waiting for "

            f"{target.stage.value} "

            f"target."

        )

    # ------------------------------------------------------------------
    # Dashboard Summary
    # ------------------------------------------------------------------

    def dashboard_summary(
            self,
            position: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Dashboard-friendly summary.
        """

        state = self.state(position)

        decision = self.calculate_partial_exit(
            position,
        )

        next_target = self.next_target(position)

        return {

            "pair":
                self.pair(position),

            "side":
                self.side(position),

            "current_r":
                round(
                    self.current_r_multiple(position),
                    2,
                ),

            "remaining_qty":
                state.remaining_quantity,

            "completed":
                [
                    stage.value
                    for stage
                    in state.completed_stages
                ],

            "next_stage":
                (
                    next_target.stage.value
                    if next_target
                    else None
                ),

            "execute":
                decision.execute,

            "message":
                decision.message,

        }

    # ------------------------------------------------------------------
    # Readiness Check
    # ------------------------------------------------------------------

    def ready(
            self,
            position: Dict[str, Any],
    ) -> bool:
        """
        Convenience method.

        Returns True when the manager
        is ready to execute a partial exit.
        """

        decision = self.calculate_partial_exit(
            position,
        )

        return (

                decision.execute

                and

                len(

                    self.validate_decision(

                        position,

                        decision,

                    )

                ) == 0

        )

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def preview(
            self,
            position: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Preview the next execution without
        sending an order.
        """

        decision = self.calculate_partial_exit(
            position,
        )

        return {

            "ready":
                self.ready(position),

            "decision":
                decision.to_dict(),

            "next_action":
                self.next_action(position),

            "progress":
                self.progress(position),

        }

    # ------------------------------------------------------------------
    # Execute Single Position
    # ------------------------------------------------------------------

    def manage_position(
            self,
            position: Dict[str, Any],
    ) -> Optional[ExecutionContext]:
        """
        Execute a staged partial-profit exit.

        This is the ONLY method that performs execution.

        Workflow

            Evaluate Position

                    │

                    ▼

            Calculate Decision

                    │

                    ▼

            Validate Decision

                    │

                    ▼

            PositionManager.close_partial_position()

                    │

                    ▼

            Execution Framework

                    │

                    ▼

            ExecutionContext
        """

        self._metrics["positions_evaluated"] += 1

        #
        # Determine what should happen.
        #

        decision = self.calculate_partial_exit(
            position,
        )

        if not decision.execute:
            self._metrics["positions_skipped"] += 1

            return None

        #
        # Validate the execution.
        #

        validation = self.validate_decision(

            position,

            decision,

        )

        if validation:
            logger.warning(

                "Partial profit validation failed: %s",

                validation,

            )

            self._metrics["positions_skipped"] += 1

            return None

        #
        # Execute through Position Management.
        #
        # IMPORTANT:
        #
        # No SQL.
        #
        # No repository access.
        #
        # No direct position updates.
        #

        try:

            context = (

                self.position_manager.close_partial_position(

                    position_id=self.position_id(
                        position,
                    ),

                    quantity=decision.quantity,

                    stage=decision.stage.value,

                    reason="PARTIAL_PROFIT",

                )

            )

        except Exception:

            self._metrics["errors"] += 1

            logger.exception(

                "Partial profit execution failed."

            )

            return None

        #
        # Update runtime metrics.
        #

        self._metrics["partial_exits"] += 1

        if decision.stage == PartialProfitStage.FIRST:

            self._metrics["stage1"] += 1

        elif decision.stage == PartialProfitStage.SECOND:

            self._metrics["stage2"] += 1

        elif decision.stage == PartialProfitStage.THIRD:

            self._metrics["stage3"] += 1

        elif decision.stage == PartialProfitStage.FINAL:

            self._metrics["final"] += 1

        #
        # Attach metadata for downstream
        # dashboards and execution analytics.
        #

        try:

            context.metadata.setdefault(

                "partial_profit",

                {},

            )

            context.metadata["partial_profit"].update(

                {

                    "stage":
                        decision.stage.value,

                    "quantity":
                        decision.quantity,

                    "quantity_percent":
                        decision.quantity_percent,

                    "achieved_rr":
                        decision.achieved_rr,

                    "target_price":
                        decision.target_price,

                    "remaining_position_pct":

                        self.remaining_position_pct(
                            position,
                        ),

                    "method":

                        self.config.method.value,

                    "decision":

                        decision.to_dict(),

                }

            )

        except Exception:

            #
            # Metadata is optional.
            #

            pass

        logger.info(

            "Executed %s partial profit for %s (qty=%s)",

            decision.stage.value,

            self.position_id(position),

            decision.quantity,

        )

        return context

    # ------------------------------------------------------------------
    # Execution Verification
    # ------------------------------------------------------------------

    def verify_execution(
            self,
            context: ExecutionContext,
    ) -> bool:
        """
        Basic verification hook.

        Later sprints can extend this to verify:

            • POSITION_PARTIALLY_CLOSED event

            • Snapshot refresh

            • Position projection

            • Account balances

            • Execution latency
        """

        if context is None:
            return False

        try:

            if hasattr(

                    context,

                    "warnings",

            ):
                return len(context.warnings) == 0

        except Exception:

            pass

        return True

    # ------------------------------------------------------------------
    # Execution Summary
    # ------------------------------------------------------------------

    def execution_summary(
            self,
            position: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Preview what would happen if execution
        occurred right now.
        """

        decision = self.calculate_partial_exit(

            position,

        )

        validation = self.validate_decision(

            position,

            decision,

        )

        return {

            "ready":

                decision.execute

                and

                len(validation) == 0,

            "decision":

                decision.to_dict(),

            "validation":

                validation,

            "position_id":

                self.position_id(position),

            "pair":

                self.pair(position),

            "remaining_quantity":

                self.remaining_quantity(position),

        }

    # ------------------------------------------------------------------
    # Batch Position Management
    # ------------------------------------------------------------------

    def manage_positions(
            self,
            positions: List[Dict[str, Any]],
    ) -> List[ExecutionContext]:
        """
        Evaluate and manage multiple positions.

        Each position is processed independently. A failure affecting one
        position does not stop processing of the remaining positions.
        """

        contexts: List[ExecutionContext] = []

        if not positions:
            return contexts

        logger.info(
            "Evaluating %d positions for partial-profit exits.",
            len(positions),
        )

        for position in positions:

            position_id = self.position_id(position)

            try:

                context = self.manage_position(
                    position,
                )

                if context is not None:
                    contexts.append(
                        context,
                    )

            except Exception as exc:

                self._metrics["errors"] += 1

                logger.exception(
                    "Partial-profit management failed for position %s: %s",
                    position_id,
                    exc,
                )

        logger.info(
            "Partial-profit batch complete: "
            "%d position(s) modified from %d evaluated.",
            len(contexts),
            len(positions),
        )

        return contexts

    # ------------------------------------------------------------------
    # Account Management
    # ------------------------------------------------------------------

    def manage_account(
            self,
            *,
            account_id: str,
    ) -> List[ExecutionContext]:
        """
        Run partial-profit management for every position belonging to an
        account.

        Position loading and refresh remain the responsibility of
        ForexPositionManagementEngine.
        """

        if not account_id:
            raise ValueError(
                "account_id is required."
            )

        positions = self.position_manager.refresh_positions(
            account_id=account_id,
        )

        if not positions:
            logger.info(
                "No positions found for account %s.",
                account_id,
            )

            return []

        return self.manage_positions(
            positions,
        )

    # ------------------------------------------------------------------
    # Portfolio Management
    # ------------------------------------------------------------------

    def manage_portfolio(
            self,
            *,
            portfolio_id: str,
    ) -> List[ExecutionContext]:
        """
        Run partial-profit management for every position belonging to a
        portfolio.
        """

        if not portfolio_id:
            raise ValueError(
                "portfolio_id is required."
            )

        positions = self.position_manager.load_positions(
            portfolio_id=portfolio_id,
        )

        if not positions:
            logger.info(
                "No positions found for portfolio %s.",
                portfolio_id,
            )

            return []

        return self.manage_positions(
            positions,
        )

    # ------------------------------------------------------------------
    # Account Preview
    # ------------------------------------------------------------------

    def preview_account(
            self,
            *,
            account_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Preview partial-profit decisions for an account without executing
        any position changes.
        """

        if not account_id:
            raise ValueError(
                "account_id is required."
            )

        positions = self.position_manager.load_positions(
            account_id=account_id,
        )

        previews: List[Dict[str, Any]] = []

        for position in positions:

            try:

                preview = self.preview(
                    position,
                )

                preview["position_id"] = self.position_id(
                    position,
                )

                preview["pair"] = self.pair(
                    position,
                )

                previews.append(
                    preview,
                )

            except Exception as exc:

                previews.append(
                    {
                        "position_id": self.position_id(position),
                        "pair": self.pair(position),
                        "ready": False,
                        "error": str(exc),
                    }
                )

        return previews

    # ------------------------------------------------------------------
    # Portfolio Preview
    # ------------------------------------------------------------------

    def preview_portfolio(
            self,
            *,
            portfolio_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Preview partial-profit decisions for a portfolio without executing
        any position changes.
        """

        if not portfolio_id:
            raise ValueError(
                "portfolio_id is required."
            )

        positions = self.position_manager.load_positions(
            portfolio_id=portfolio_id,
        )

        previews: List[Dict[str, Any]] = []

        for position in positions:

            try:

                preview = self.preview(
                    position,
                )

                preview["position_id"] = self.position_id(
                    position,
                )

                preview["pair"] = self.pair(
                    position,
                )

                previews.append(
                    preview,
                )

            except Exception as exc:

                previews.append(
                    {
                        "position_id": self.position_id(position),
                        "pair": self.pair(position),
                        "ready": False,
                        "error": str(exc),
                    }
                )

        return previews

    # ------------------------------------------------------------------
    # Manage Selected Positions
    # ------------------------------------------------------------------

    def manage_position_ids(
            self,
            position_ids: List[str],
    ) -> List[ExecutionContext]:
        """
        Manage a caller-supplied list of position identifiers.

        Missing positions are skipped and logged.
        """

        contexts: List[ExecutionContext] = []

        for position_id in position_ids or []:

            if not position_id:
                continue

            try:

                position = self.position_manager.load_position(
                    position_id,
                )

                if position is None:
                    logger.warning(
                        "Partial-profit position not found: %s",
                        position_id,
                    )

                    self._metrics["positions_skipped"] += 1

                    continue

                context = self.manage_position(
                    position,
                )

                if context is not None:
                    contexts.append(
                        context,
                    )

            except Exception as exc:

                self._metrics["errors"] += 1

                logger.exception(
                    "Partial-profit processing failed for %s: %s",
                    position_id,
                    exc,
                )

        return contexts

    # ------------------------------------------------------------------

    def __str__(
            self,
    ) -> str:
        return self.__repr__()

# ==============================================================================
# Singleton Factory
# ==============================================================================

_PARTIAL_PROFIT_MANAGER: Optional[
    ForexPartialProfitManager
] = None

def get_forex_partial_profit_manager(
        *,
        db,
        portfolio_engine=None,
        config: Optional[
            PartialProfitConfig
        ] = None,
        cache: bool = True,
) -> ForexPartialProfitManager:
    """
    Singleton factory.

    Trade Management Engine should always obtain
    the manager through this function.
    """

    global _PARTIAL_PROFIT_MANAGER

    if (

            not cache

            or

            _PARTIAL_PROFIT_MANAGER is None

    ):
        _PARTIAL_PROFIT_MANAGER = (

            ForexPartialProfitManager(

                db=db,

                portfolio_engine=portfolio_engine,

                config=config,

            )

        )

    return _PARTIAL_PROFIT_MANAGER