"""
==============================================================================
forex_trade_alert_manager.py

Sprint FX-3
Institutional Trade Alert Manager

This manager evaluates live position state and produces trade-management
alerts such as:

    • STOP_HIT
    • TARGET_HIT
    • DRAWDOWN_WARNING
    • MARGIN_WARNING
    • VOLATILITY_WARNING
    • TIME_WARNING

Architecture

ForexTradeManagementEngine
            │
            ▼
ForexTradeAlertManager
            │
            ▼
ForexTradeManagementAlert

This manager NEVER:

    • Executes trades
    • Closes positions
    • Writes SQL
    • Modifies position objects directly

It only evaluates positions and returns alert objects.
=============================================================================="""

from __future__ import annotations

import logging
import math
import uuid

from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from enum import Enum
from typing import Any
from typing import Dict
from typing import List
from typing import Optional


logger = logging.getLogger(__name__)


# ==============================================================================
# Helpers
# ==============================================================================


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        if value is None:
            return default

        result = float(value)

        if math.isnan(result) or math.isinf(result):
            return default

        return result

    except Exception:
        return default


# ==============================================================================
# Alert Types
# ==============================================================================


class TradeAlertType(str, Enum):

    STOP_HIT = "STOP_HIT"

    TARGET_HIT = "TARGET_HIT"

    DRAWDOWN_WARNING = "DRAWDOWN_WARNING"

    MARGIN_WARNING = "MARGIN_WARNING"

    VOLATILITY_WARNING = "VOLATILITY_WARNING"

    TIME_WARNING = "TIME_WARNING"

    AI_WARNING = "AI_WARNING"

    INFO = "INFO"


class TradeAlertSeverity(str, Enum):

    LOW = "LOW"

    MEDIUM = "MEDIUM"

    HIGH = "HIGH"

    CRITICAL = "CRITICAL"


# ==============================================================================
# Alert Model
# ==============================================================================


@dataclass
class ForexTradeAlert:

    alert_id: str

    alert_type: str

    severity: str

    message: str

    position_id: Optional[str]

    account_id: Optional[str]

    portfolio_id: Optional[str]

    tenant_id: Optional[str]

    user_id: Optional[str]

    pair: Optional[str]

    side: Optional[str]

    current_price: float

    stop_price: Optional[float]

    target_price: Optional[float]

    unrealized_pnl: float

    notional_value: float

    drawdown_pct: float

    created_at: datetime

    raw: Optional[Dict[str, Any]] = None

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        data = asdict(self)

        data["created_at"] = self.created_at.isoformat()

        return data


# ==============================================================================
# Configuration
# ==============================================================================


@dataclass
class TradeAlertConfig:

    enabled: bool = True

    #
    # Core lifecycle alerts
    #
    enable_stop_alerts: bool = True

    enable_target_alerts: bool = True

    enable_drawdown_alerts: bool = True

    #
    # Institutional alerts
    #
    enable_margin_alerts: bool = True

    enable_volatility_alerts: bool = False

    enable_time_alerts: bool = False

    enable_ai_alerts: bool = False

    #
    # Drawdown warning threshold
    #
    drawdown_threshold_pct: float = 0.03

    #
    # Margin warning threshold
    #
    margin_utilization_threshold: float = 0.80

    #
    # Maximum holding time in hours
    #
    max_holding_hours: float = 72.0

    #
    # Duplicate suppression
    #
    suppress_duplicates: bool = True


# ==============================================================================
# Manager
# ==============================================================================


class ForexTradeAlertManager:
    """
    Position lifecycle alert evaluator.

    This manager only evaluates position state and returns alerts.

    Trade closure remains the responsibility of
    ForexTradeManagementEngine.
    """

    def __init__(
        self,
        *,
        config: Optional[TradeAlertConfig] = None,
    ):

        self.config = config or TradeAlertConfig()

        self.reset_metrics()

    # ------------------------------------------------------------------
    # Position Access
    # ------------------------------------------------------------------

    @staticmethod
    def value(
        position: Any,
        key: str,
        default: Any = None,
    ) -> Any:

        if isinstance(position, dict):
            return position.get(key, default)

        return getattr(position, key, default)

    # ------------------------------------------------------------------

    @classmethod
    def position_id(
        cls,
        position: Any,
    ) -> Optional[str]:

        return (
            cls.value(position, "position_id")
            or cls.value(position, "id")
        )

    # ------------------------------------------------------------------

    @classmethod
    def account_id(
        cls,
        position: Any,
    ) -> Optional[str]:

        return cls.value(position, "account_id")

    # ------------------------------------------------------------------

    @classmethod
    def portfolio_id(
        cls,
        position: Any,
    ) -> Optional[str]:

        return cls.value(position, "portfolio_id")

    # ------------------------------------------------------------------

    @classmethod
    def tenant_id(
        cls,
        position: Any,
    ) -> Optional[str]:

        return cls.value(position, "tenant_id")

    # ------------------------------------------------------------------

    @classmethod
    def user_id(
        cls,
        position: Any,
    ) -> Optional[str]:

        return cls.value(position, "user_id")

    # ------------------------------------------------------------------

    @classmethod
    def pair(
        cls,
        position: Any,
    ) -> Optional[str]:

        return (
            cls.value(position, "pair")
            or cls.value(position, "symbol")
        )

    # ------------------------------------------------------------------

    @classmethod
    def side(
        cls,
        position: Any,
    ) -> str:

        return str(
            cls.value(position, "side", "")
        ).upper()

    # ------------------------------------------------------------------

    @classmethod
    def current_price(
        cls,
        position: Any,
    ) -> float:

        return _safe_float(
            cls.value(position, "current_price")
        )

    # ------------------------------------------------------------------

    @classmethod
    def stop_price(
        cls,
        position: Any,
    ) -> Optional[float]:

        value = cls.value(position, "stop_price")

        if value is None:
            return None

        return _safe_float(value)

    # ------------------------------------------------------------------

    @classmethod
    def target_price(
        cls,
        position: Any,
    ) -> Optional[float]:

        value = cls.value(position, "target_price")

        if value is None:
            return None

        return _safe_float(value)

    # ------------------------------------------------------------------

    @classmethod
    def unrealized_pnl(
        cls,
        position: Any,
    ) -> float:

        return _safe_float(
            cls.value(position, "unrealized_pnl")
        )

    # ------------------------------------------------------------------

    @classmethod
    def notional_value(
        cls,
        position: Any,
    ) -> float:

        return _safe_float(
            cls.value(position, "notional_value")
        )

    # ------------------------------------------------------------------

    @staticmethod
    def to_dict(
        position: Any,
    ) -> Dict[str, Any]:

        if isinstance(position, dict):
            return dict(position)

        if hasattr(position, "to_dict"):
            return position.to_dict()

        if hasattr(position, "__dict__"):
            return dict(position.__dict__)

        return {}

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def reset_metrics(
        self,
    ) -> None:

        self._metrics = {

            "positions_evaluated": 0,

            "alerts_generated": 0,

            "stop_alerts": 0,

            "target_alerts": 0,

            "drawdown_alerts": 0,

            "margin_alerts": 0,

            "volatility_alerts": 0,

            "time_alerts": 0,

            "ai_alerts": 0,

            "errors": 0,

            "last_run": None,

        }

    # ------------------------------------------------------------------
    # Public API Placeholders
    # ------------------------------------------------------------------

    def evaluate_position(
        self,
        position: Any,
    ) -> Optional[ForexTradeAlert]:
        """
        Part 2.
        """
        raise NotImplementedError()

    # ------------------------------------------------------------------

    def evaluate_positions(
        self,
        positions: List[Any],
    ) -> List[ForexTradeAlert]:
        """
        Part 3.
        """
        raise NotImplementedError()

    # ------------------------------------------------------------------

    def health(
        self,
    ) -> Dict[str, Any]:
        """
        Part 3.
        """
        raise NotImplementedError()

    # ------------------------------------------------------------------

    def statistics(
        self,
    ) -> Dict[str, Any]:
        """
        Part 3.
        """
        raise NotImplementedError()

    # ------------------------------------------------------------------
    # Alert Builders
    # ------------------------------------------------------------------

    def _create_alert(
        self,
        *,
        position: Any,
        alert_type: TradeAlertType,
        severity: TradeAlertSeverity,
        message: str,
        drawdown_pct: float = 0.0,
    ) -> ForexTradeAlert:
        """
        Construct a ForexTradeAlert from the supplied position.
        """

        self._metrics["alerts_generated"] += 1

        return ForexTradeAlert(

            alert_id=str(uuid.uuid4()),

            alert_type=alert_type.value,

            severity=severity.value,

            message=message,

            position_id=self.position_id(position),

            account_id=self.account_id(position),

            portfolio_id=self.portfolio_id(position),

            tenant_id=self.tenant_id(position),

            user_id=self.user_id(position),

            pair=self.pair(position),

            side=self.side(position),

            current_price=self.current_price(position),

            stop_price=self.stop_price(position),

            target_price=self.target_price(position),

            unrealized_pnl=self.unrealized_pnl(position),

            notional_value=self.notional_value(position),

            drawdown_pct=drawdown_pct,

            created_at=_utc_now(),

            raw=self.to_dict(position),

        )

    # ------------------------------------------------------------------
    # Stop Hit
    # ------------------------------------------------------------------

    def _evaluate_stop_hit(
        self,
        position: Any,
    ) -> Optional[ForexTradeAlert]:

        if not self.config.enable_stop_alerts:

            return None

        stop = self.stop_price(position)

        if stop is None:

            return None

        current = self.current_price(position)

        side = self.side(position)

        stop_hit = (

            current <= stop

            if side in {

                "BUY",

                "LONG",

            }

            else

            current >= stop

        )

        if not stop_hit:

            return None

        self._metrics["stop_alerts"] += 1

        return self._create_alert(

            position=position,

            alert_type=TradeAlertType.STOP_HIT,

            severity=TradeAlertSeverity.CRITICAL,

            message="Stop price reached.",

        )

    # ------------------------------------------------------------------
    # Target Hit
    # ------------------------------------------------------------------

    def _evaluate_target_hit(
        self,
        position: Any,
    ) -> Optional[ForexTradeAlert]:

        if not self.config.enable_target_alerts:

            return None

        target = self.target_price(position)

        if target is None:

            return None

        current = self.current_price(position)

        side = self.side(position)

        target_hit = (

            current >= target

            if side in {

                "BUY",

                "LONG",

            }

            else

            current <= target

        )

        if not target_hit:

            return None

        self._metrics["target_alerts"] += 1

        return self._create_alert(

            position=position,

            alert_type=TradeAlertType.TARGET_HIT,

            severity=TradeAlertSeverity.HIGH,

            message="Profit target reached.",

        )

    # ------------------------------------------------------------------
    # Drawdown
    # ------------------------------------------------------------------

    def _evaluate_drawdown(
        self,
        position: Any,
    ) -> Optional[ForexTradeAlert]:

        if not self.config.enable_drawdown_alerts:

            return None

        pnl = self.unrealized_pnl(position)

        if pnl >= 0:

            return None

        notional = max(

            self.notional_value(position),

            1.0,

        )

        drawdown = abs(pnl) / notional

        if drawdown < self.config.drawdown_threshold_pct:

            return None

        self._metrics["drawdown_alerts"] += 1

        return self._create_alert(

            position=position,

            alert_type=TradeAlertType.DRAWDOWN_WARNING,

            severity=TradeAlertSeverity.MEDIUM,

            message=(
                f"Drawdown exceeds "
                f"{self.config.drawdown_threshold_pct:.1%} "
                f"of notional."
            ),

            drawdown_pct=drawdown,

        )

    # ------------------------------------------------------------------
    # Main Evaluation
    # ------------------------------------------------------------------

    def evaluate_position(
        self,
        position: Any,
    ) -> Optional[ForexTradeAlert]:
        """
        Evaluate a position and return the
        highest-priority trade alert.

        Priority

            STOP_HIT

            TARGET_HIT

            DRAWDOWN_WARNING
        """

        self._metrics["positions_evaluated"] += 1

        try:

            #
            # Highest priority
            #

            alert = self._evaluate_stop_hit(
                position,
            )

            if alert:

                return alert

            #
            # Second priority
            #

            alert = self._evaluate_target_hit(
                position,
            )

            if alert:

                return alert

            #
            # Lowest priority
            #

            alert = self._evaluate_drawdown(
                position,
            )

            if alert:

                return alert

            return None

        except Exception:

            self._metrics["errors"] += 1

            logger.exception(

                "Trade alert evaluation failed."

            )

            return None

    # ------------------------------------------------------------------
    # Explain
    # ------------------------------------------------------------------

    def explain(
        self,
        position: Any,
    ) -> Dict[str, Any]:
        """
        Returns diagnostic information
        explaining alert evaluation.
        """

        stop = self._evaluate_stop_hit(position)

        target = self._evaluate_target_hit(position)

        drawdown = self._evaluate_drawdown(position)

        return {

            "position_id":

                self.position_id(position),

            "pair":

                self.pair(position),

            "side":

                self.side(position),

            "current_price":

                self.current_price(position),

            "stop_price":

                self.stop_price(position),

            "target_price":

                self.target_price(position),

            "unrealized_pnl":

                self.unrealized_pnl(position),

            "notional":

                self.notional_value(position),

            "stop_hit":

                stop is not None,

            "target_hit":

                target is not None,

            "drawdown_warning":

                drawdown is not None,

            "generated_alert":

                (
                    stop.alert_type
                    if stop
                    else target.alert_type
                    if target
                    else drawdown.alert_type
                    if drawdown
                    else None
                ),

        }
    # ------------------------------------------------------------------
    # Batch Evaluation
    # ------------------------------------------------------------------

    def evaluate_positions(
        self,
        positions: List[Any],
    ) -> List[ForexTradeAlert]:
        """
        Evaluate every supplied position.

        Returns
        -------
        List[ForexTradeAlert]

        One alert per position (highest priority only).
        """

        alerts: List[ForexTradeAlert] = []

        if not positions:

            return alerts

        logger.info(

            "Evaluating %d positions for trade alerts.",

            len(positions),

        )

        for position in positions:

            try:

                alert = self.evaluate_position(
                    position,
                )

                if alert is not None:

                    alerts.append(
                        alert,
                    )

            except Exception:

                self._metrics["errors"] += 1

                logger.exception(

                    "Trade alert evaluation failed."

                )

        self._metrics["last_run"] = (

            _utc_now().isoformat()

        )

        logger.info(

            "Generated %d trade alerts.",

            len(alerts),

        )

        return alerts

    # ------------------------------------------------------------------
    # Dry Run
    # ------------------------------------------------------------------

    def dry_run(
        self,
        position: Any,
    ) -> Dict[str, Any]:
        """
        Evaluate a position without
        producing side effects.
        """

        report = self.explain(
            position,
        )

        report["evaluation_complete"] = True

        report["manager"] = (

            "ForexTradeAlertManager"

        )

        return report

    # ------------------------------------------------------------------
    # Runtime Metrics
    # ------------------------------------------------------------------

    def metrics(
        self,
    ) -> Dict[str, Any]:
        """
        Returns a copy of the runtime metrics.
        """

        return dict(
            self._metrics,
        )

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def statistics(
        self,
    ) -> Dict[str, Any]:
        """
        Operational statistics for dashboards.
        """

        metrics = self.metrics()

        return {

            "manager":

                "ForexTradeAlertManager",

            "enabled":

                self.config.enabled,

            "positions_evaluated":

                metrics["positions_evaluated"],

            "alerts_generated":

                metrics["alerts_generated"],

            "stop_alerts":

                metrics["stop_alerts"],

            "target_alerts":

                metrics["target_alerts"],

            "drawdown_alerts":

                metrics["drawdown_alerts"],

            "margin_alerts":

                metrics["margin_alerts"],

            "volatility_alerts":

                metrics["volatility_alerts"],

            "time_alerts":

                metrics["time_alerts"],

            "ai_alerts":

                metrics["ai_alerts"],

            "errors":

                metrics["errors"],

            "last_run":

                metrics["last_run"],

        }

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health(
        self,
    ) -> Dict[str, Any]:
        """
        Health information for
        Operations Dashboard.
        """

        return {

            "manager":

                "ForexTradeAlertManager",

            "status":

                "healthy",

            "enabled":

                self.config.enabled,

            "configuration": {

                "stop_alerts":

                    self.config.enable_stop_alerts,

                "target_alerts":

                    self.config.enable_target_alerts,

                "drawdown_alerts":

                    self.config.enable_drawdown_alerts,

                "margin_alerts":

                    self.config.enable_margin_alerts,

                "volatility_alerts":

                    self.config.enable_volatility_alerts,

                "time_alerts":

                    self.config.enable_time_alerts,

                "ai_alerts":

                    self.config.enable_ai_alerts,

            },

            "metrics":

                self.metrics(),

        }

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def update_configuration(
        self,
        **kwargs,
    ) -> None:
        """
        Runtime configuration updates.
        """

        for key, value in kwargs.items():

            if hasattr(

                self.config,

                key,

            ):

                setattr(

                    self.config,

                    key,

                    value,

                )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_configuration(
        self,
    ) -> List[str]:
        """
        Validate configuration values.
        """

        warnings: List[str] = []

        if self.config.drawdown_threshold_pct <= 0:

            warnings.append(

                "drawdown_threshold_pct must be greater than zero."

            )

        if (

            self.config.margin_utilization_threshold <= 0

            or

            self.config.margin_utilization_threshold > 1

        ):

            warnings.append(

                "margin_utilization_threshold should be between 0 and 1."

            )

        if self.config.max_holding_hours <= 0:

            warnings.append(

                "max_holding_hours must be greater than zero."

            )

        return warnings

    # ------------------------------------------------------------------
    # Process
    # ------------------------------------------------------------------

    def process(
        self,
        positions: List[Any],
    ) -> List[ForexTradeAlert]:
        """
        Primary processing entry point.

        This method is intended to be called by
        ForexTradeManagementEngine.
        """

        logger.info(

            "Starting trade alert evaluation."

        )

        alerts = self.evaluate_positions(
            positions,
        )

        logger.info(

            "Trade alert evaluation complete."

        )

        return alerts

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(
        self,
    ) -> None:
        """
        Reset runtime metrics.
        """

        self.reset_metrics()

    # ------------------------------------------------------------------
    # Representation
    # ------------------------------------------------------------------

    def __repr__(
        self,
    ) -> str:

        return (

            f"ForexTradeAlertManager("

            f"enabled={self.config.enabled}, "

            f"alerts={self._metrics['alerts_generated']})"

        )

    # ------------------------------------------------------------------

    def __str__(
        self,
    ) -> str:

        return self.__repr__()


# ==============================================================================
# Factory
# ==============================================================================

_TRADE_ALERT_MANAGER = None


def get_forex_trade_alert_manager(
    *,
    config: Optional[TradeAlertConfig] = None,
    cache: bool = True,
) -> ForexTradeAlertManager:

    global _TRADE_ALERT_MANAGER

    if (
        not cache
        or _TRADE_ALERT_MANAGER is None
    ):

        _TRADE_ALERT_MANAGER = ForexTradeAlertManager(
            config=config,
        )

    return _TRADE_ALERT_MANAGER