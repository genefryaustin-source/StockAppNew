"""
==============================================================================
forex_break_even_manager.py

Sprint FX Phase 2A

Institutional Break-Even Manager

Responsibilities
----------------
• Monitor open positions
• Determine break-even eligibility
• Calculate break-even stop price
• Delegate all position modifications to
  ForexPositionManagementEngine
• Never write directly to the database
• Never mutate position objects directly

Architecture
------------

ForexTradeManagementEngine
            │
            ▼
ForexBreakEvenManager
            │
            ▼
ForexPositionManagementEngine
            │
            ▼
ExecutionService
            │
            ▼
Execution Pipeline
            │
            ▼
Repositories
=============================================================================="""

from __future__ import annotations

import logging

from dataclasses import dataclass

from datetime import datetime

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
# Configuration
# ==============================================================================


@dataclass
class BreakEvenConfig:
    """
    Configuration controlling automatic
    break-even management.
    """

    enabled: bool = True

    #
    # Minimum profit (pips)
    #
    trigger_pips: float = 25.0

    #
    # Additional pips beyond entry.
    #
    offset_pips: float = 0.0

    #
    # Require an existing stop loss.
    #
    require_existing_stop: bool = True

    #
    # Only move to BE once.
    #
    only_once: bool = True

    #
    # Ignore manual stop changes
    #
    respect_manual_adjustments: bool = True

    #
    # Ignore already protected trades
    #
    skip_protected_positions: bool = True


# ==============================================================================
# Break Even Manager
# ==============================================================================


class ForexBreakEvenManager:

    """
    Institutional Break-Even Manager.

    This class NEVER:

        • executes trades
        • writes SQL
        • updates repositories
        • records execution events

    Instead it delegates every
    modification through the
    Position Management Engine.
    """

    def __init__(
        self,
        *,
        db,
        portfolio_engine=None,
        config: Optional[BreakEvenConfig] = None,
    ):

        self.db = db

        self.config = config or BreakEvenConfig()

        self.position_manager: ForexPositionManagementEngine = (
            get_forex_position_management_engine(
                db=db,
                portfolio_engine=portfolio_engine,
                actor="break_even_manager",
                source="FOREX",
            )
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def pip_size(
        pair: str,
    ) -> float:
        """
        Returns the pip size
        for the supplied FX pair.
        """

        pair = (pair or "").upper()

        if "JPY" in pair:
            return 0.01

        return 0.0001

    # ------------------------------------------------------------------

    @staticmethod
    def current_profit_pips(
        *,
        side: str,
        entry: float,
        current: float,
        pair: str,
    ) -> float:
        """
        Calculates current
        unrealized profit in pips.
        """

        pip = ForexBreakEvenManager.pip_size(pair)

        side = (side or "").upper()

        if side in ("BUY", "LONG"):

            return (

                current - entry

            ) / pip

        return (

            entry - current

        ) / pip

    # ------------------------------------------------------------------

    def enabled(self) -> bool:
        """
        Returns whether the manager
        is enabled.
        """

        return bool(self.config.enabled)

    # ------------------------------------------------------------------

    def health(
        self,
    ) -> Dict[str, Any]:

        return {

            "manager": "ForexBreakEvenManager",

            "enabled": self.config.enabled,

            "trigger_pips": self.config.trigger_pips,

            "offset_pips": self.config.offset_pips,

            "require_existing_stop":
                self.config.require_existing_stop,

            "only_once":
                self.config.only_once,

            "position_manager":
                self.position_manager is not None,

            "timestamp":
                datetime.utcnow().isoformat(),

        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Position Management
    # ------------------------------------------------------------------

    def manage_position(
            self,
            position: Dict[str, Any],
    ) -> Optional[ExecutionContext]:
        """
        Evaluate a single position for automatic
        break-even management.

        Returns
        -------
        ExecutionContext
            When the stop was successfully moved.

        None
            When no action was required.
        """

        #
        # Eligibility
        #

        if not self.eligible(position):
            return None

        position_id = self._position_id(position)

        if not position_id:
            logger.warning(
                "Break-even skipped: missing position id."
            )
            return None

        break_even_price = self.calculate_break_even_price(
            position,
        )

        logger.info(

            "Moving %s to break-even %.5f",

            position_id,

            break_even_price,

        )

        try:

            #
            # NEVER modify the position directly.
            #
            # Always delegate through the Position Manager.
            #

            context = self.position_manager.modify_position(

                position_id,

                stop_price=break_even_price,

            )

            #
            # Attach metadata for downstream
            # dashboards and diagnostics.
            #

            try:

                context.metadata.setdefault(
                    "break_even",
                    {},
                )

                context.metadata["break_even"].update(

                    {

                        "applied": True,

                        "trigger_pips":
                            self.config.trigger_pips,

                        "offset_pips":
                            self.config.offset_pips,

                        "new_stop":
                            break_even_price,

                        "timestamp":
                            datetime.utcnow().isoformat(),

                    }

                )

            except Exception:

                #
                # Metadata is optional.
                #

                pass

            logger.info(

                "Break-even applied successfully to %s",

                position_id,

            )

            return context

        except Exception as exc:

            logger.exception(

                "Break-even failed for %s",

                position_id,

            )

            logger.exception(exc)

            return None

    # ------------------------------------------------------------------

    def manage_positions(
            self,
            positions: List[Dict[str, Any]],
    ) -> List[ExecutionContext]:
        """
        Batch processing for all open positions.
        """

        results: List[
            ExecutionContext
        ] = []

        if not positions:
            return results

        logger.info(

            "Evaluating %d positions for break-even.",

            len(positions),

        )

        for position in positions:

            try:

                context = self.manage_position(
                    position,
                )

                if context is not None:
                    results.append(
                        context,
                    )

            except Exception as exc:

                logger.exception(exc)

        logger.info(

            "Break-even adjustments applied: %d",

            len(results),

        )

        return results

    # ------------------------------------------------------------------
    # Account Processing
    # ------------------------------------------------------------------

    def manage_account(
            self,
            *,
            account_id: str,
    ) -> List[ExecutionContext]:
        """
        Runs break-even management for
        every position in an account.
        """

        positions = self.position_manager.refresh_positions(

            account_id=account_id,

        )

        return self.manage_positions(
            positions,
        )

    # ------------------------------------------------------------------
    # Portfolio Processing
    # ------------------------------------------------------------------

    def manage_portfolio(
            self,
            *,
            portfolio_id: str,
    ) -> List[ExecutionContext]:
        """
        Runs break-even management for
        every position in a portfolio.
        """

        positions = self.position_manager.load_positions(

            portfolio_id=portfolio_id,

        )

        return self.manage_positions(
            positions,
        )

    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Position Field Access
    # ------------------------------------------------------------------

    @staticmethod
    def _value(
            position: Any,
            key: str,
            default: Any = None,
    ) -> Any:
        """
        Supports both dictionaries and object-style position models.
        """

        if isinstance(position, dict):
            return position.get(key, default)

        return getattr(position, key, default)

    # ------------------------------------------------------------------

    @staticmethod
    def _position_id(
            position: Any,
    ) -> Optional[str]:

        return (
                ForexBreakEvenManager._value(position, "position_id")
                or ForexBreakEvenManager._value(position, "id")
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _pair(
            position: Any,
    ) -> str:

        return (
                ForexBreakEvenManager._value(position, "pair")
                or ForexBreakEvenManager._value(position, "symbol")
                or ""
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _entry_price(
            position: Any,
    ) -> float:

        return float(
            ForexBreakEvenManager._value(
                position,
                "avg_entry_price",
                ForexBreakEvenManager._value(
                    position,
                    "avg_price",
                    ForexBreakEvenManager._value(
                        position,
                        "entry_price",
                        0.0,
                    ),
                ),
            )
            or 0.0
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _current_price(
            position: Any,
    ) -> float:

        return float(
            ForexBreakEvenManager._value(
                position,
                "current_price",
                ForexBreakEvenManager._entry_price(position),
            )
            or 0.0
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _side(
            position: Any,
    ) -> str:

        return str(
            ForexBreakEvenManager._value(
                position,
                "side",
                "",
            )
        ).upper()

    # ------------------------------------------------------------------

    @staticmethod
    def _stop_price(
            position: Any,
    ) -> Optional[float]:

        stop = ForexBreakEvenManager._value(
            position,
            "stop_price",
        )

        if stop is None:
            return None

        try:
            return float(stop)
        except Exception:
            return None

    # ------------------------------------------------------------------

    @staticmethod
    def _status(
            position: Any,
    ) -> str:

        return str(
            ForexBreakEvenManager._value(
                position,
                "status",
                "",
            )
        ).upper()

    # ------------------------------------------------------------------
    # Eligibility
    # ------------------------------------------------------------------

    def eligible(
            self,
            position: Dict[str, Any],
    ) -> bool:
        """
        Determines whether a position qualifies for break-even.

        Rules:
            • Manager must be enabled.
            • Position must be open.
            • Entry and current price must be valid.
            • Existing stop may be required.
            • Position must have reached trigger pips.
            • Stop must not already be beyond break-even.
        """

        if not self.enabled():
            return False

        status = self._status(position)

        if status and status not in {
            "OPEN",
            "ACTIVE",
            "LIVE",
            "FILLED",
        }:
            return False

        position_id = self._position_id(position)

        if not position_id:
            return False

        pair = self._pair(position)

        side = self._side(position)

        if side not in {
            "BUY",
            "SELL",
            "LONG",
            "SHORT",
        }:
            return False

        entry = self._entry_price(position)

        current = self._current_price(position)

        if entry <= 0 or current <= 0:
            return False

        stop = self._stop_price(position)

        if self.config.require_existing_stop and stop is None:
            return False

        profit_pips = self.current_profit_pips(
            side=side,
            entry=entry,
            current=current,
            pair=pair,
        )

        if profit_pips < self.config.trigger_pips:
            return False

        break_even = self.calculate_break_even_price(
            position,
        )

        #
        # If already protected beyond break-even, skip.
        #

        if stop is not None and self.config.skip_protected_positions:

            if side in {"BUY", "LONG"} and stop >= break_even:
                return False

            if side in {"SELL", "SHORT"} and stop <= break_even:
                return False

        return True

    # ------------------------------------------------------------------
    # Break-Even Price
    # ------------------------------------------------------------------

    def calculate_break_even_price(
            self,
            position: Dict[str, Any],
    ) -> float:
        """
        Calculates the break-even stop price.

        BUY/LONG:
            entry + offset

        SELL/SHORT:
            entry - offset
        """

        pair = self._pair(position)

        side = self._side(position)

        entry = self._entry_price(position)

        pip = self.pip_size(pair)

        offset = self.config.offset_pips * pip

        if side in {
            "BUY",
            "LONG",
        }:
            return round(
                entry + offset,
                5,
            )

        return round(
            entry - offset,
            5,
        )

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def explain(
            self,
            position: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Returns a diagnostic explanation of break-even eligibility.
        Useful for dashboards and debugging.
        """

        pair = self._pair(position)

        side = self._side(position)

        entry = self._entry_price(position)

        current = self._current_price(position)

        stop = self._stop_price(position)

        profit_pips = 0.0

        if entry > 0 and current > 0:
            profit_pips = self.current_profit_pips(
                side=side,
                entry=entry,
                current=current,
                pair=pair,
            )

        break_even = None

        try:
            break_even = self.calculate_break_even_price(
                position,
            )
        except Exception:
            pass

        return {

            "enabled": self.enabled(),

            "position_id": self._position_id(position),

            "pair": pair,

            "side": side,

            "status": self._status(position),

            "entry": entry,

            "current": current,

            "stop": stop,

            "trigger_pips": self.config.trigger_pips,

            "offset_pips": self.config.offset_pips,

            "profit_pips": round(
                profit_pips,
                2,
            ),

            "break_even_price": break_even,

            "eligible": self.eligible(
                position,
            ),

        }
    # ------------------------------------------------------------------
    # Runtime Metrics
    # ------------------------------------------------------------------

    def reset_metrics(self) -> None:
        """
        Reset runtime statistics.
        """

        self._metrics = {

            "positions_evaluated": 0,

            "positions_eligible": 0,

            "positions_modified": 0,

            "positions_skipped": 0,

            "errors": 0,

            "last_run": None,

            "last_duration_ms": 0.0,

        }

    # ------------------------------------------------------------------

    def metrics(
        self,
    ) -> Dict[str, Any]:
        """
        Current runtime metrics.
        """

        if not hasattr(self, "_metrics"):

            self.reset_metrics()

        return dict(self._metrics)

    # ------------------------------------------------------------------

    def _increment(
        self,
        metric: str,
        value: int = 1,
    ) -> None:

        if not hasattr(self, "_metrics"):

            self.reset_metrics()

        self._metrics[metric] = (

            self._metrics.get(metric, 0)

            + value

        )

    # ------------------------------------------------------------------
    # Dry Run
    # ------------------------------------------------------------------

    def dry_run(
        self,
        position: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Evaluate a position without making
        any changes.
        """

        report = self.explain(position)

        report["action"] = (

            "MOVE_TO_BREAK_EVEN"

            if report["eligible"]

            else

            "NO_ACTION"

        )

        return report

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_configuration(
        self,
    ) -> List[str]:

        warnings: List[str] = []

        if self.config.trigger_pips <= 0:

            warnings.append(

                "trigger_pips should be greater than zero."

            )

        if self.config.offset_pips < 0:

            warnings.append(

                "offset_pips cannot be negative."

            )

        return warnings

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def update_configuration(
        self,
        **kwargs,
    ) -> None:

        for key, value in kwargs.items():

            if hasattr(self.config, key):

                setattr(

                    self.config,

                    key,

                    value,

                )

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def statistics(
        self,
    ) -> Dict[str, Any]:

        metrics = self.metrics()

        return {

            "manager":

                "ForexBreakEvenManager",

            "enabled":

                self.config.enabled,

            "trigger_pips":

                self.config.trigger_pips,

            "offset_pips":

                self.config.offset_pips,

            "positions_evaluated":

                metrics["positions_evaluated"],

            "positions_modified":

                metrics["positions_modified"],

            "positions_skipped":

                metrics["positions_skipped"],

            "errors":

                metrics["errors"],

            "last_run":

                metrics["last_run"],

        }

    # ------------------------------------------------------------------
    # Integration Hook
    # ------------------------------------------------------------------

    def process(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ) -> List[ExecutionContext]:
        """
        Primary entry point used by
        ForexTradeManagementEngine.
        """

        import time

        if not hasattr(self, "_metrics"):

            self.reset_metrics()

        start = time.perf_counter()

        try:

            if account_id:

                results = self.manage_account(

                    account_id=account_id,

                )

            elif portfolio_id:

                results = self.manage_portfolio(

                    portfolio_id=portfolio_id,

                )

            else:

                results = []

        except Exception:

            self._increment("errors")

            raise

        elapsed = (

            time.perf_counter()

            - start

        ) * 1000

        self._metrics["last_run"] = (

            datetime.utcnow().isoformat()

        )

        self._metrics["last_duration_ms"] = round(

            elapsed,

            2,

        )

        return results

    # ------------------------------------------------------------------
    # Enhanced Health
    # ------------------------------------------------------------------

    def health(
        self,
    ) -> Dict[str, Any]:

        return {

            "manager":

                "ForexBreakEvenManager",

            "status":

                "healthy",

            "enabled":

                self.config.enabled,

            "trigger_pips":

                self.config.trigger_pips,

            "offset_pips":

                self.config.offset_pips,

            "require_existing_stop":

                self.config.require_existing_stop,

            "only_once":

                self.config.only_once,

            "position_manager":

                self.position_manager is not None,

            "metrics":

                self.metrics(),

        }


# ==============================================================================
# Factory
# ==============================================================================

_BREAK_EVEN_MANAGER = None


def get_forex_break_even_manager(
    *,
    db,
    portfolio_engine=None,
    config: Optional[BreakEvenConfig] = None,
    cache: bool = True,
) -> ForexBreakEvenManager:

    global _BREAK_EVEN_MANAGER

    if (

        not cache

        or

        _BREAK_EVEN_MANAGER is None

    ):

        _BREAK_EVEN_MANAGER = (

            ForexBreakEvenManager(

                db=db,

                portfolio_engine=portfolio_engine,

                config=config,

            )

        )

    return _BREAK_EVEN_MANAGER
