"""
==============================================================================
forex_trailing_stop_manager.py

Sprint FX-2
Institutional Trailing Stop Manager

This manager is responsible for automatically tightening stop losses while
positions move into profit.

Architecture

ForexTradeManagementEngine
            │
            ▼
ForexTrailingStopManager
            │
            ▼
ForexPositionManagementEngine
            │
            ▼
ExecutionService
            │
            ▼
Execution Framework

The manager NEVER:

    • Executes trades
    • Writes SQL
    • Updates repositories
    • Modifies position objects directly

Every position modification is delegated to:

    ForexPositionManagementEngine.modify_position()

=============================================================================="""

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
# Trailing Stop Methods
# ==============================================================================


class TrailingMethod(str, Enum):

    PERCENT = "PERCENT"

    FIXED_PIPS = "FIXED_PIPS"

    ATR = "ATR"

    SWING = "SWING"

    VOLATILITY = "VOLATILITY"


# ==============================================================================
# Configuration
# ==============================================================================


@dataclass
class TrailingStopConfig:
    """
    Configuration for institutional
    trailing stop management.
    """

    enabled: bool = True

    #
    # Trailing algorithm
    #
    method: TrailingMethod = TrailingMethod.PERCENT

    #
    # Percent trailing
    #
    trailing_percent: float = 0.01

    #
    # Fixed pip distance
    #
    trailing_pips: float = 20.0

    #
    # ATR multiplier
    #
    atr_multiplier: float = 2.0

    #
    # Swing lookback
    #
    swing_lookback: int = 10

    #
    # Historical volatility multiplier
    #
    volatility_multiplier: float = 1.5

    #
    # Never loosen stops
    #
    tighten_only: bool = True

    #
    # Ignore manual adjustments
    #
    respect_manual_adjustments: bool = True

    #
    # Enable diagnostics
    #
    diagnostics: bool = False


# ==============================================================================
# Manager
# ==============================================================================


class ForexTrailingStopManager:
    """
    Institutional trailing stop manager.

    Responsibilities

        • Determine eligibility

        • Calculate new stop

        • Delegate update through
          Position Management Engine

        • Never modify a position directly
    """

    def __init__(
        self,
        *,
        db,
        portfolio_engine=None,
        config: Optional[TrailingStopConfig] = None,
    ):

        self.db = db

        self.config = config or TrailingStopConfig()

        self.position_manager: ForexPositionManagementEngine = (
            get_forex_position_management_engine(
                db=db,
                portfolio_engine=portfolio_engine,
                actor="trailing_stop_manager",
                source="FOREX",
            )
        )

        self.reset_metrics()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def value(
        position: Any,
        key: str,
        default=None,
    ):

        if isinstance(position, dict):

            return position.get(key, default)

        return getattr(position, key, default)

    # ------------------------------------------------------------------

    @staticmethod
    def position_id(
        position: Any,
    ) -> Optional[str]:

        return (

            ForexTrailingStopManager.value(
                position,
                "position_id",
            )

            or

            ForexTrailingStopManager.value(
                position,
                "id",
            )

        )

    # ------------------------------------------------------------------

    @staticmethod
    def pair(
        position: Any,
    ) -> str:

        return (

            ForexTrailingStopManager.value(
                position,
                "pair",
            )

            or

            ForexTrailingStopManager.value(
                position,
                "symbol",
                "",
            )

        )

    # ------------------------------------------------------------------

    @staticmethod
    def side(
        position: Any,
    ) -> str:

        return str(

            ForexTrailingStopManager.value(
                position,
                "side",
                "",
            )

        ).upper()

    # ------------------------------------------------------------------

    @staticmethod
    def entry_price(
        position: Any,
    ) -> float:

        return float(

            ForexTrailingStopManager.value(

                position,

                "avg_entry_price",

                ForexTrailingStopManager.value(

                    position,

                    "entry_price",

                    0.0,

                ),

            )

            or 0.0

        )

    # ------------------------------------------------------------------

    @staticmethod
    def current_price(
        position: Any,
    ) -> float:

        return float(

            ForexTrailingStopManager.value(

                position,

                "current_price",

                0.0,

            )

            or 0.0

        )

    # ------------------------------------------------------------------

    @staticmethod
    def stop_price(
        position: Any,
    ) -> Optional[float]:

        stop = ForexTrailingStopManager.value(
            position,
            "stop_price",
        )

        if stop is None:

            return None

        return float(stop)

    # ------------------------------------------------------------------

    @staticmethod
    def pip_size(
        pair: str,
    ) -> float:

        pair = (pair or "").upper()

        if "JPY" in pair:

            return 0.01

        return 0.0001

    # ------------------------------------------------------------------

    def enabled(
        self,
    ) -> bool:

        return bool(self.config.enabled)

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
        Determines whether a position is eligible for trailing stop
        management.
        """

        if not self.enabled():
            return False

        position_id = self.position_id(position)

        if not position_id:
            return False

        status = str(
            self.value(position, "status", "")
        ).upper()

        if status and status not in {
            "OPEN",
            "ACTIVE",
            "LIVE",
            "FILLED",
        }:
            return False

        side = self.side(position)

        if side not in {
            "BUY",
            "SELL",
            "LONG",
            "SHORT",
        }:
            return False

        current = self.current_price(position)

        if current <= 0:
            return False

        return True

    # ------------------------------------------------------------------
    # Stop Calculation
    # ------------------------------------------------------------------

    def calculate_stop(
            self,
            position: Dict[str, Any],
    ) -> float:
        """
        Dispatch trailing stop calculation based on configured method.
        """

        method = self.config.method

        if isinstance(method, str):
            method = TrailingMethod(method.upper())

        if method == TrailingMethod.PERCENT:
            return self._calculate_percent_stop(position)

        if method == TrailingMethod.FIXED_PIPS:
            return self._calculate_fixed_pip_stop(position)

        if method == TrailingMethod.ATR:
            return self._calculate_atr_stop(position)

        if method == TrailingMethod.SWING:
            return self._calculate_swing_stop(position)

        if method == TrailingMethod.VOLATILITY:
            return self._calculate_volatility_stop(position)

        return self._calculate_percent_stop(position)

    # ------------------------------------------------------------------

    def _calculate_percent_stop(
            self,
            position: Dict[str, Any],
    ) -> float:

        current = self.current_price(position)

        distance = abs(
            current * self.config.trailing_percent
        )

        return self._stop_from_distance(
            position,
            distance,
        )

    # ------------------------------------------------------------------

    def _calculate_fixed_pip_stop(
            self,
            position: Dict[str, Any],
    ) -> float:

        pair = self.pair(position)

        pip = self.pip_size(pair)

        distance = (
                self.config.trailing_pips
                * pip
        )

        return self._stop_from_distance(
            position,
            distance,
        )

    # ------------------------------------------------------------------

    def _calculate_atr_stop(
            self,
            position: Dict[str, Any],
    ) -> float:
        """
        ATR trailing stop.

        Uses position-provided ATR fields when available:

            atr
            atr_14
            volatility_atr

        If ATR is unavailable, falls back to fixed-pip trailing.
        """

        atr = (
                self.value(position, "atr")
                or self.value(position, "atr_14")
                or self.value(position, "volatility_atr")
        )

        try:
            atr = float(atr)
        except Exception:
            atr = 0.0

        if atr <= 0:
            return self._calculate_fixed_pip_stop(
                position,
            )

        distance = (
                atr
                * self.config.atr_multiplier
        )

        return self._stop_from_distance(
            position,
            distance,
        )

    # ------------------------------------------------------------------

    def _calculate_swing_stop(
            self,
            position: Dict[str, Any],
    ) -> float:
        """
        Swing trailing stop.

        Uses precomputed swing fields if available:

            swing_low
            swing_high

        BUY/LONG trails under swing_low.
        SELL/SHORT trails above swing_high.

        Falls back to fixed-pip trailing when unavailable.
        """

        side = self.side(position)

        if side in {
            "BUY",
            "LONG",
        }:

            swing_low = self.value(
                position,
                "swing_low",
            )

            try:
                swing_low = float(swing_low)
            except Exception:
                swing_low = 0.0

            if swing_low > 0:
                return round(
                    swing_low,
                    5,
                )

        else:

            swing_high = self.value(
                position,
                "swing_high",
            )

            try:
                swing_high = float(swing_high)
            except Exception:
                swing_high = 0.0

            if swing_high > 0:
                return round(
                    swing_high,
                    5,
                )

        return self._calculate_fixed_pip_stop(
            position,
        )

    # ------------------------------------------------------------------

    def _calculate_volatility_stop(
            self,
            position: Dict[str, Any],
    ) -> float:
        """
        Volatility trailing stop.

        Uses available volatility fields:

            volatility
            realized_volatility
            historical_volatility

        Volatility is treated as a price-distance input when present.
        """

        volatility = (
                self.value(position, "volatility")
                or self.value(position, "realized_volatility")
                or self.value(position, "historical_volatility")
        )

        try:
            volatility = float(volatility)
        except Exception:
            volatility = 0.0

        if volatility <= 0:
            return self._calculate_fixed_pip_stop(
                position,
            )

        distance = (
                volatility
                * self.config.volatility_multiplier
        )

        return self._stop_from_distance(
            position,
            distance,
        )

    # ------------------------------------------------------------------

    def _stop_from_distance(
            self,
            position: Dict[str, Any],
            distance: float,
    ) -> float:

        current = self.current_price(position)

        side = self.side(position)

        if side in {
            "BUY",
            "LONG",
        }:

            stop = current - abs(distance)

        else:

            stop = current + abs(distance)

        return round(
            stop,
            5,
        )

    # ------------------------------------------------------------------
    # Tightening Rules
    # ------------------------------------------------------------------

    def should_update_stop(
            self,
            position: Dict[str, Any],
            new_stop: float,
    ) -> bool:
        """
        Determines whether the calculated stop should be applied.
        """

        existing = self.stop_price(position)

        if existing is None:
            return True

        if not self.config.tighten_only:
            return True

        side = self.side(position)

        if side in {
            "BUY",
            "LONG",
        }:
            return new_stop > existing

        return new_stop < existing

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def explain(
            self,
            position: Dict[str, Any],
    ) -> Dict[str, Any]:

        eligible = self.eligible(position)

        new_stop = None

        should_update = False

        if eligible:

            try:
                new_stop = self.calculate_stop(
                    position,
                )
                should_update = self.should_update_stop(
                    position,
                    new_stop,
                )
            except Exception:
                new_stop = None
                should_update = False

        return {

            "manager": "ForexTrailingStopManager",

            "enabled": self.enabled(),

            "method": str(self.config.method),

            "position_id": self.position_id(position),

            "pair": self.pair(position),

            "side": self.side(position),

            "current_price": self.current_price(position),

            "existing_stop": self.stop_price(position),

            "calculated_stop": new_stop,

            "eligible": eligible,

            "should_update": should_update,

            "tighten_only": self.config.tighten_only,

            "trailing_percent": self.config.trailing_percent,

            "trailing_pips": self.config.trailing_pips,

            "atr_multiplier": self.config.atr_multiplier,

            "volatility_multiplier": self.config.volatility_multiplier,

        }

    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Position Management
    # ------------------------------------------------------------------

    def manage_position(
            self,
            position: Dict[str, Any],
    ) -> Optional[ExecutionContext]:
        """
        Evaluate a single position and apply an updated
        trailing stop when appropriate.

        All updates are delegated to the
        ForexPositionManagementEngine.

        No SQL or repository access occurs here.
        """

        self._metrics["positions_evaluated"] += 1

        if not self.eligible(position):
            self._metrics["positions_skipped"] += 1

            return None

        try:

            new_stop = self.calculate_stop(position)

            if not self.should_update_stop(
                    position,
                    new_stop,
            ):
                self._metrics["positions_skipped"] += 1

                return None

            context = self.position_manager.modify_position(

                self.position_id(position),

                stop_price=new_stop,

            )

            #
            # Attach diagnostics for downstream dashboards.
            #

            try:

                context.metadata.setdefault(
                    "trailing_stop",
                    {},
                )

                context.metadata["trailing_stop"].update(

                    {

                        "method": str(self.config.method),

                        "new_stop": new_stop,

                        "tighten_only":
                            self.config.tighten_only,

                        "updated_at":
                            datetime.utcnow().isoformat(),

                    }

                )

            except Exception:

                pass

            self._metrics["positions_modified"] += 1

            logger.info(

                "Trailing stop updated for %s",

                self.position_id(position),

            )

            return context

        except Exception as exc:

            self._metrics["errors"] += 1

            logger.exception(exc)

            return None

    # ------------------------------------------------------------------

    def manage_positions(
            self,
            positions: List[Dict[str, Any]],
    ) -> List[ExecutionContext]:
        """
        Batch processing for multiple positions.
        """

        contexts: List[ExecutionContext] = []

        if not positions:
            return contexts

        logger.info(

            "Evaluating %d positions for trailing stop updates.",

            len(positions),

        )

        for position in positions:

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

                logger.exception(exc)

        logger.info(

            "Trailing stop adjustments applied: %d",

            len(contexts),

        )

        return contexts

    # ------------------------------------------------------------------
    # Account Processing
    # ------------------------------------------------------------------

    def manage_account(
            self,
            *,
            account_id: str,
    ) -> List[ExecutionContext]:
        """
        Process every open position
        within an account.
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
        Process every open position
        within a portfolio.
        """

        positions = self.position_manager.load_positions(

            portfolio_id=portfolio_id,

        )

        return self.manage_positions(

            positions,

        )

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def dry_run(
            self,
            position: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Evaluate a position without
        modifying it.
        """

        report = self.explain(position)

        report["action"] = (

            "UPDATE_TRAILING_STOP"

            if report["should_update"]

            else

            "NO_ACTION"

        )

        return report

    # ------------------------------------------------------------------

    def validate_configuration(
            self,
    ) -> List[str]:
        """
        Validate configuration values.
        """

        warnings: List[str] = []

        if self.config.trailing_percent <= 0:
            warnings.append(

                "Trailing percent must be greater than zero."

            )

        if self.config.trailing_pips <= 0:
            warnings.append(

                "Trailing pips must be greater than zero."

            )

        if self.config.atr_multiplier <= 0:
            warnings.append(

                "ATR multiplier must be greater than zero."

            )

        if self.config.swing_lookback < 2:
            warnings.append(

                "Swing lookback should be at least 2."

            )

        return warnings

    # ------------------------------------------------------------------

    def update_configuration(
            self,
            **kwargs,
    ) -> None:
        """
        Update runtime configuration.
        """

        for key, value in kwargs.items():

            if hasattr(self.config, key):
                setattr(

                    self.config,

                    key,

                    value,

                )

    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Runtime Statistics
    # ------------------------------------------------------------------

    def metrics(
            self,
    ) -> Dict[str, Any]:
        """
        Returns a copy of the runtime metrics.
        """

        return dict(self._metrics)

    # ------------------------------------------------------------------

    def statistics(
            self,
    ) -> Dict[str, Any]:
        """
        Operational statistics used by
        dashboards and health monitoring.
        """

        metrics = self.metrics()

        return {

            "manager":
                "ForexTrailingStopManager",

            "enabled":
                self.config.enabled,

            "method":
                str(self.config.method),

            "tighten_only":
                self.config.tighten_only,

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

            "last_duration_ms":
                metrics["last_duration_ms"],

        }

    # ------------------------------------------------------------------

    def health(
            self,
    ) -> Dict[str, Any]:
        """
        Health information consumed by the
        Operations Dashboard.
        """

        validation = self.validate_configuration()

        return {

            "manager":
                "ForexTrailingStopManager",

            "status":
                "healthy" if len(validation) == 0 else "warning",

            "enabled":
                self.config.enabled,

            "method":
                str(self.config.method),

            "position_manager":
                self.position_manager is not None,

            "configuration_warnings":
                validation,

            "metrics":
                self.metrics(),

        }

    # ------------------------------------------------------------------

    def process(
            self,
            *,
            account_id: Optional[str] = None,
            portfolio_id: Optional[str] = None,
    ) -> List[ExecutionContext]:
        """
        Primary entry point called by the
        Forex Trade Management Engine.

        Only one of account_id or
        portfolio_id should be supplied.
        """

        import time

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

            self._metrics["errors"] += 1

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

    def reset(
            self,
    ) -> None:
        """
        Reset runtime statistics.
        """

        self.reset_metrics()

    # ------------------------------------------------------------------

    def __repr__(
            self,
    ) -> str:

        return (

            f"ForexTrailingStopManager("

            f"enabled={self.config.enabled}, "

            f"method={self.config.method}, "

            f"modified={self._metrics['positions_modified']})"

        )

    # ------------------------------------------------------------------

    def __str__(
            self,
    ) -> str:

        return self.__repr__()


# ==============================================================================
# Factory
# ==============================================================================

_TRAILING_MANAGER = None


def get_forex_trailing_stop_manager(
    *,
    db,
    portfolio_engine=None,
    config: Optional[
        TrailingStopConfig
    ] = None,
    cache: bool = True,
) -> ForexTrailingStopManager:

    global _TRAILING_MANAGER

    if (

        not cache

        or

        _TRAILING_MANAGER is None

    ):

        _TRAILING_MANAGER = (

            ForexTrailingStopManager(

                db=db,

                portfolio_engine=portfolio_engine,

                config=config,

            )

        )

    return _TRAILING_MANAGER