# modules/forex/forex_trading_engine.py

from __future__ import annotations

import json
import logging
import math
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import text
try:
    from modules.forex.forex_service import ForexService, get_forex_service, normalize_pair, split_pair
    from modules.forex.forex_ai import ForexAIEngine, get_forex_ai_engine
    from modules.forex.forex_portfolio_engine import ForexPortfolioEngine, get_forex_portfolio_engine
except Exception:
    from forex_service import ForexService, get_forex_service, normalize_pair, split_pair
    from forex_ai import ForexAIEngine, get_forex_ai_engine
    from forex_portfolio_engine import ForexPortfolioEngine, get_forex_portfolio_engine


logger = logging.getLogger(__name__)

ORDER_TYPES = {"MARKET", "LIMIT", "STOP", "STOP_LIMIT", "TAKE_PROFIT", "TRAILING_STOP"}
ORDER_SIDES = {"BUY", "SELL"}
ORDER_STATUSES = {
    "PENDING",
    "SUBMITTED",
    "FILLED",
    "PARTIALLY_FILLED",
    "CANCELLED",
    "REJECTED",
    "EXPIRED",
}

DEFAULT_BROKER = "paper"
DEFAULT_TIF = "DAY"
DEFAULT_MAX_RISK_PER_TRADE = 0.02
DEFAULT_MAX_PAIR_EXPOSURE = 0.15
DEFAULT_MAX_PORTFOLIO_EXPOSURE = 0.75
DEFAULT_MAX_LEVERAGE = 20.0


@dataclass
class ForexOrder:
    order_id: str
    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]
    account_id: str
    pair: str
    side: str
    order_type: str
    units: float
    status: str
    tif: str
    broker: str
    limit_price: Optional[float]
    stop_price: Optional[float]
    target_price: Optional[float]
    trailing_amount: Optional[float]
    avg_fill_price: Optional[float]
    filled_units: float
    remaining_units: float
    estimated_slippage: float
    actual_slippage: float
    signal_id: Optional[str]
    recommendation: Optional[str]
    confidence: Optional[float]
    composite_score: Optional[float]
    rejection_reason: Optional[str]
    created_at: datetime
    updated_at: datetime
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        for key in ["created_at", "updated_at", "submitted_at", "filled_at", "cancelled_at"]:
            if data.get(key):
                data[key] = data[key].isoformat()
        return data


@dataclass
class ForexTrade:
    trade_id: str
    order_id: str
    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]
    account_id: str
    position_id: Optional[str]
    pair: str
    side: str
    units: float
    entry_price: float
    stop_price: Optional[float]
    target_price: Optional[float]
    realized_pnl: float
    unrealized_pnl: float
    broker: str
    status: str
    opened_at: datetime
    closed_at: Optional[datetime] = None
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["opened_at"] = self.opened_at.isoformat()
        if self.closed_at:
            data["closed_at"] = self.closed_at.isoformat()
        return data


@dataclass
class ForexExecution:
    execution_id: str
    order_id: str
    trade_id: Optional[str]
    pair: str
    side: str
    units: float
    price: float
    broker: str
    slippage: float
    executed_at: datetime
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["executed_at"] = self.executed_at.isoformat()
        return data


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _naive(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    return value.replace(tzinfo=None)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        result = float(value)
        if math.isnan(result) or math.isinf(result):
            return default
        return result
    except Exception:
        return default


def _json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(json.dumps(value, default=str))
    except Exception:
        return {"value": str(value)}


class ForexRiskManager:
    def __init__(
        self,
        portfolio_engine: ForexPortfolioEngine,
        *,
        max_risk_per_trade: float = DEFAULT_MAX_RISK_PER_TRADE,
        max_pair_exposure: float = DEFAULT_MAX_PAIR_EXPOSURE,
        max_portfolio_exposure: float = DEFAULT_MAX_PORTFOLIO_EXPOSURE,
        max_leverage: float = DEFAULT_MAX_LEVERAGE,
    ) -> None:
        self.portfolio_engine = portfolio_engine
        self.max_risk_per_trade = max_risk_per_trade
        self.max_pair_exposure = max_pair_exposure
        self.max_portfolio_exposure = max_portfolio_exposure
        self.max_leverage = max_leverage

    def validate_order(self, order: ForexOrder) -> Tuple[bool, str]:
        account = self.portfolio_engine.get_account(account_id=order.account_id)
        if not account:
            return False, "Forex account not found."

        if order.units <= 0:
            return False, "Order units must be positive."

        if order.side not in ORDER_SIDES:
            return False, "Invalid order side."

        if order.order_type not in ORDER_TYPES:
            return False, "Invalid order type."

        quote = self.portfolio_engine.forex_service.get_quote(order.pair)
        price = _safe_float(order.limit_price or quote.price)
        notional = order.units * price

        if account.equity <= 0:
            return False, "Account equity must be positive."

        if account.leverage > self.max_leverage:
            return False, "Account leverage exceeds Forex max leverage limit."

        pair_exposure = notional / account.equity
        if pair_exposure > self.max_pair_exposure:
            return False, "Order exceeds max pair exposure."

        snapshot = self.portfolio_engine.get_snapshot(
            account_id=order.account_id,
            persist=False,
            refresh=True,
        )
        current_total_notional = snapshot.total_notional if snapshot else 0.0
        total_exposure = (current_total_notional + notional) / account.equity

        if total_exposure > self.max_portfolio_exposure:
            return False, "Order exceeds max portfolio Forex exposure."

        margin_required = notional / max(account.leverage, 1.0)
        if margin_required > account.margin_available:
            return False, "Insufficient margin available."

        if order.stop_price:
            risk_per_unit = abs(price - order.stop_price)
            estimated_risk = risk_per_unit * order.units
            if estimated_risk > account.equity * self.max_risk_per_trade:
                return False, "Order exceeds max risk per trade."

        return True, "OK"


class ForexExecutionEngine:
    def __init__(self, forex_service: ForexService) -> None:
        self.forex_service = forex_service

    def calculate_slippage(self, expected_price: float, fill_price: float) -> float:
        if expected_price <= 0:
            return 0.0
        return (fill_price - expected_price) / expected_price

    def should_fill(self, order: ForexOrder, current_price: float) -> bool:
        if order.order_type == "MARKET":
            return True

        if order.order_type == "LIMIT":
            if order.side == "BUY":
                return current_price <= _safe_float(order.limit_price)
            return current_price >= _safe_float(order.limit_price)

        if order.order_type in {"STOP", "STOP_LIMIT"}:
            if order.side == "BUY":
                return current_price >= _safe_float(order.stop_price)
            return current_price <= _safe_float(order.stop_price)

        if order.order_type == "TAKE_PROFIT":
            if order.side == "BUY":
                return current_price >= _safe_float(order.target_price)
            return current_price <= _safe_float(order.target_price)

        return False

    def execute_order(self, order: ForexOrder) -> Optional[ForexExecution]:
        quote = self.forex_service.get_quote(order.pair)
        current_price = _safe_float(quote.price)

        if current_price <= 0:
            return None

        if not self.should_fill(order, current_price):
            return None

        expected_price = _safe_float(order.limit_price or order.stop_price or current_price)
        slippage = self.calculate_slippage(expected_price, current_price)

        return ForexExecution(
            execution_id=str(uuid.uuid4()),
            order_id=order.order_id,
            trade_id=None,
            pair=order.pair,
            side=order.side,
            units=order.units,
            price=current_price,
            broker=order.broker,
            slippage=slippage,
            executed_at=_utc_now(),
            raw={"quote": quote.to_dict()},
        )


class ForexTradeAttributionEngine:
    def __init__(self, db: Any = None) -> None:
        self.db = db

    def record_attribution(
        self,
        *,
        tenant_id: Optional[str],
        user_id: Optional[str],
        portfolio_id: Optional[str],
        order: ForexOrder,
        trade: ForexTrade,
    ) -> None:
        if self.db is None:
            return

        self.db.execute(text(
            """
            INSERT INTO forex_trade_attribution (
                tenant_id, user_id, portfolio_id, order_id, trade_id, pair,
                signal_id, recommendation, confidence, composite_score,
                payload, created_at
            )
            VALUES (
                :tenant_id, :user_id, :portfolio_id, :order_id, :trade_id, :pair,
                :signal_id, :recommendation, :confidence, :composite_score,
                :payload, :created_at
            )
            """),
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "portfolio_id": portfolio_id,
                "order_id": order.order_id,
                "trade_id": trade.trade_id,
                "pair": order.pair,
                "signal_id": order.signal_id,
                "recommendation": order.recommendation,
                "confidence": order.confidence,
                "composite_score": order.composite_score,
                "payload": _json({"order": order.to_dict(), "trade": trade.to_dict()}),
                "created_at": _naive(_utc_now()),
            },
        )


class ForexTradingEngine:
    def __init__(
        self,
        *,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        db: Any = None,
        forex_service: Optional[ForexService] = None,
        forex_ai_engine: Optional[ForexAIEngine] = None,
        forex_portfolio_engine: Optional[ForexPortfolioEngine] = None,
        broker: str = DEFAULT_BROKER,
    ) -> None:
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.portfolio_id = portfolio_id
        self.db = db
        self.broker = broker

        self.forex_service = forex_service or get_forex_service(
            tenant_id=tenant_id,
            user_id=user_id,
            db=db,
        )
        self.forex_ai_engine = forex_ai_engine or get_forex_ai_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            db=db,
            forex_service=self.forex_service,
        )
        self.forex_portfolio_engine = forex_portfolio_engine or get_forex_portfolio_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
            forex_service=self.forex_service,
            forex_ai_engine=self.forex_ai_engine,
        )

        self.risk_manager = ForexRiskManager(self.forex_portfolio_engine)
        self.execution_engine = ForexExecutionEngine(self.forex_service)
        self.attribution_engine = ForexTradeAttributionEngine(db)

    def ensure_tables(self) -> None:
        if self.db is None:
            return

        self.db.execute(text(
            """
            CREATE TABLE IF NOT EXISTS forex_orders (
                order_id VARCHAR(64) PRIMARY KEY,
                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),
                account_id VARCHAR(64),
                pair VARCHAR(20),
                side VARCHAR(10),
                order_type VARCHAR(40),
                units DOUBLE PRECISION,
                status VARCHAR(40),
                tif VARCHAR(20),
                broker VARCHAR(80),
                limit_price DOUBLE PRECISION,
                stop_price DOUBLE PRECISION,
                target_price DOUBLE PRECISION,
                trailing_amount DOUBLE PRECISION,
                avg_fill_price DOUBLE PRECISION,
                filled_units DOUBLE PRECISION,
                remaining_units DOUBLE PRECISION,
                estimated_slippage DOUBLE PRECISION,
                actual_slippage DOUBLE PRECISION,
                signal_id VARCHAR(100),
                recommendation VARCHAR(40),
                confidence DOUBLE PRECISION,
                composite_score DOUBLE PRECISION,
                rejection_reason TEXT,
                raw_payload JSONB,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                submitted_at TIMESTAMP WITHOUT TIME ZONE,
                filled_at TIMESTAMP WITHOUT TIME ZONE,
                cancelled_at TIMESTAMP WITHOUT TIME ZONE
            )
            """
        ))

        self.db.execute(text(
            """
            CREATE TABLE IF NOT EXISTS forex_trades (
                trade_id VARCHAR(64) PRIMARY KEY,
                order_id VARCHAR(64),
                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),
                account_id VARCHAR(64),
                position_id VARCHAR(64),
                pair VARCHAR(20),
                side VARCHAR(10),
                units DOUBLE PRECISION,
                entry_price DOUBLE PRECISION,
                stop_price DOUBLE PRECISION,
                target_price DOUBLE PRECISION,
                realized_pnl DOUBLE PRECISION,
                unrealized_pnl DOUBLE PRECISION,
                broker VARCHAR(80),
                status VARCHAR(40),
                raw_payload JSONB,
                opened_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP WITHOUT TIME ZONE
            )
            """
        ))

        self.db.execute(text(
            """
            CREATE TABLE IF NOT EXISTS forex_trade_executions (
                execution_id VARCHAR(64) PRIMARY KEY,
                order_id VARCHAR(64),
                trade_id VARCHAR(64),
                pair VARCHAR(20),
                side VARCHAR(10),
                units DOUBLE PRECISION,
                price DOUBLE PRECISION,
                broker VARCHAR(80),
                slippage DOUBLE PRECISION,
                raw_payload JSONB,
                executed_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """
        ))

        self.db.execute(text(
            """
            CREATE TABLE IF NOT EXISTS forex_trade_attribution (
                id SERIAL PRIMARY KEY,
                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),
                order_id VARCHAR(64),
                trade_id VARCHAR(64),
                pair VARCHAR(20),
                signal_id VARCHAR(100),
                recommendation VARCHAR(40),
                confidence DOUBLE PRECISION,
                composite_score DOUBLE PRECISION,
                payload JSONB,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """
        ))

        self.db.execute(text(
            """
            CREATE TABLE IF NOT EXISTS forex_trade_audit_log (
                id SERIAL PRIMARY KEY,
                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),
                account_id VARCHAR(64),
                order_id VARCHAR(64),
                trade_id VARCHAR(64),
                event_type VARCHAR(80),
                message TEXT,
                payload JSONB,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """
        ))

        self.db.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_forex_orders_tenant_account ON forex_orders (tenant_id, account_id)"
        ))
        self.db.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_forex_trades_tenant_account ON forex_trades (tenant_id, account_id)"
        ))

        if hasattr(self.db, "commit"):
            self.db.commit()

    def submit_order(
        self,
        *,
        account_id: str,
        pair: str,
        side: str,
        order_type: str = "MARKET",
        units: float,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        target_price: Optional[float] = None,
        trailing_amount: Optional[float] = None,
        tif: str = DEFAULT_TIF,
        use_ai: bool = True,
    ) -> ForexOrder:
        self.ensure_tables()

        normalized_pair = normalize_pair(pair)
        normalized_side = side.upper().strip()
        normalized_order_type = order_type.upper().strip()
        now = _utc_now()

        signal_id = None
        recommendation = None
        confidence = None
        composite_score = None

        if use_ai:
            try:
                signal = self.forex_ai_engine.generate_signal(normalized_pair, save=True)
                signal_id = f"{normalized_pair}-{int(now.timestamp())}"
                recommendation = signal.recommendation
                confidence = signal.confidence
                composite_score = signal.composite_score
            except Exception as exc:
                logger.warning("Forex AI signal failed during order submit: %s", exc)

        order = ForexOrder(
            order_id=str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,
            account_id=account_id,
            pair=normalized_pair,
            side=normalized_side,
            order_type=normalized_order_type,
            units=_safe_float(units),
            status="PENDING",
            tif=tif,
            broker=self.broker,
            limit_price=limit_price,
            stop_price=stop_price,
            target_price=target_price,
            trailing_amount=trailing_amount,
            avg_fill_price=None,
            filled_units=0.0,
            remaining_units=_safe_float(units),
            estimated_slippage=0.0,
            actual_slippage=0.0,
            signal_id=signal_id,
            recommendation=recommendation,
            confidence=confidence,
            composite_score=composite_score,
            rejection_reason=None,
            created_at=now,
            updated_at=now,
            raw=None,
        )

        valid, reason = self.validate_order(order)
        if not valid:
            order.status = "REJECTED"
            order.rejection_reason = reason
            self.record_order(order)
            self.record_audit_event(order=order, event_type="ORDER_REJECTED", message=reason)
            return order

        order.status = "SUBMITTED"
        order.submitted_at = _utc_now()
        order.updated_at = _utc_now()
        self.record_order(order)
        self.record_audit_event(order=order, event_type="ORDER_SUBMITTED", message="Forex order submitted.")

        if self.broker == "paper":
            self.execute_order(order.order_id)

        return self.get_order(order.order_id) or order

    def validate_order(self, order: ForexOrder) -> Tuple[bool, str]:
        return self.risk_manager.validate_order(order)

    def execute_order(self, order_id: str) -> Optional[ForexOrder]:
        order = self.get_order(order_id)
        if not order:
            return None

        if order.status not in {"PENDING", "SUBMITTED"}:
            return order

        execution = self.execution_engine.execute_order(order)
        if execution is None:
            self.record_audit_event(order=order, event_type="ORDER_NOT_FILLED", message="Order conditions not met.")
            return order

        trade = self.record_trade(order, execution)
        execution.trade_id = trade.trade_id
        self.record_execution(execution)

        position_side = "LONG" if order.side == "BUY" else "SHORT"
        position = self.forex_portfolio_engine.open_position(
            account_id=order.account_id,
            pair=order.pair,
            side=position_side,
            units=execution.units,
            entry_price=execution.price,
            stop_price=order.stop_price,
            target_price=order.target_price,
            raw={"order_id": order.order_id, "trade_id": trade.trade_id},
        )

        trade.position_id = position.id
        self.record_trade(trade=trade)

        order.status = "FILLED"
        order.filled_units = execution.units
        order.remaining_units = 0.0
        order.avg_fill_price = execution.price
        order.actual_slippage = execution.slippage
        order.filled_at = execution.executed_at
        order.updated_at = _utc_now()
        self.record_order(order)

        self.attribution_engine.record_attribution(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,
            order=order,
            trade=trade,
        )

        self.record_audit_event(
            order=order,
            trade=trade,
            event_type="ORDER_FILLED",
            message="Forex order filled through paper execution.",
        )

        if hasattr(self.db, "commit"):
            self.db.commit()

        return order

    def execute_market_order(self, **kwargs: Any) -> ForexOrder:
        kwargs["order_type"] = "MARKET"
        return self.submit_order(**kwargs)

    def execute_limit_order(self, **kwargs: Any) -> ForexOrder:
        kwargs["order_type"] = "LIMIT"
        return self.submit_order(**kwargs)

    def execute_stop_order(self, **kwargs: Any) -> ForexOrder:
        kwargs["order_type"] = "STOP"
        return self.submit_order(**kwargs)

    def cancel_order(self, order_id: str, reason: str = "Order cancelled.") -> Optional[ForexOrder]:
        order = self.get_order(order_id)
        if not order:
            return None

        if order.status in {"FILLED", "CANCELLED", "REJECTED"}:
            return order

        order.status = "CANCELLED"
        order.cancelled_at = _utc_now()
        order.updated_at = _utc_now()
        self.record_order(order)
        self.record_audit_event(order=order, event_type="ORDER_CANCELLED", message=reason)
        return order

    def modify_order(
        self,
        order_id: str,
        *,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        target_price: Optional[float] = None,
        units: Optional[float] = None,
    ) -> Optional[ForexOrder]:
        order = self.get_order(order_id)
        if not order:
            return None

        if order.status not in {"PENDING", "SUBMITTED"}:
            return order

        if limit_price is not None:
            order.limit_price = limit_price
        if stop_price is not None:
            order.stop_price = stop_price
        if target_price is not None:
            order.target_price = target_price
        if units is not None:
            order.units = _safe_float(units)
            order.remaining_units = order.units - order.filled_units

        valid, reason = self.validate_order(order)
        if not valid:
            order.status = "REJECTED"
            order.rejection_reason = reason

        order.updated_at = _utc_now()
        self.record_order(order)
        self.record_audit_event(order=order, event_type="ORDER_MODIFIED", message="Forex order modified.")
        return order

    def close_position(self, position_id: str, close_units: Optional[float] = None) -> Optional[Dict[str, Any]]:
        position = self.forex_portfolio_engine.close_position(
            position_id=position_id,
            close_units=close_units,
            notes="Closed from ForexTradingEngine.",
        )
        if not position:
            return None

        self.record_audit_event(
            account_id=position.account_id,
            trade_id=None,
            event_type="POSITION_CLOSED",
            message=f"Forex position closed: {position.pair}",
            payload=position.to_dict(),
        )
        return position.to_dict()

    def sync_positions(self, account_id: str) -> List[Dict[str, Any]]:
        positions = self.forex_portfolio_engine.refresh_positions(account_id=account_id)
        return [position.to_dict() for position in positions]

    def calculate_slippage(self, expected_price: float, fill_price: float) -> float:
        return self.execution_engine.calculate_slippage(expected_price, fill_price)

    def record_order(self, order: ForexOrder) -> None:
        if self.db is None:
            return

        self.ensure_tables()
        self.db.execute(text(
            """
            INSERT INTO forex_orders (
                order_id, tenant_id, user_id, portfolio_id, account_id, pair, side,
                order_type, units, status, tif, broker, limit_price, stop_price,
                target_price, trailing_amount, avg_fill_price, filled_units,
                remaining_units, estimated_slippage, actual_slippage, signal_id,
                recommendation, confidence, composite_score, rejection_reason,
                raw_payload, created_at, updated_at, submitted_at, filled_at, cancelled_at
            )
            VALUES (
                :order_id, :tenant_id, :user_id, :portfolio_id, :account_id, :pair, :side,
                :order_type, :units, :status, :tif, :broker, :limit_price, :stop_price,
                :target_price, :trailing_amount, :avg_fill_price, :filled_units,
                :remaining_units, :estimated_slippage, :actual_slippage, :signal_id,
                :recommendation, :confidence, :composite_score, :rejection_reason,
                :raw_payload, :created_at, :updated_at, :submitted_at, :filled_at, :cancelled_at
            )
            ON CONFLICT (order_id)
            DO UPDATE SET
                status = EXCLUDED.status,
                limit_price = EXCLUDED.limit_price,
                stop_price = EXCLUDED.stop_price,
                target_price = EXCLUDED.target_price,
                avg_fill_price = EXCLUDED.avg_fill_price,
                filled_units = EXCLUDED.filled_units,
                remaining_units = EXCLUDED.remaining_units,
                actual_slippage = EXCLUDED.actual_slippage,
                rejection_reason = EXCLUDED.rejection_reason,
                raw_payload = EXCLUDED.raw_payload,
                updated_at = EXCLUDED.updated_at,
                submitted_at = EXCLUDED.submitted_at,
                filled_at = EXCLUDED.filled_at,
                cancelled_at = EXCLUDED.cancelled_at
            """,
            {
                **order.to_dict(),
                "raw_payload": _json(order.raw or order.to_dict()),
                "created_at": _naive(order.created_at),
                "updated_at": _naive(order.updated_at),
                "submitted_at": _naive(order.submitted_at),
                "filled_at": _naive(order.filled_at),
                "cancelled_at": _naive(order.cancelled_at),
            },
        ))
        if hasattr(self.db, "commit"):
            self.db.commit()

    def record_trade(
        self,
        order: Optional[ForexOrder] = None,
        execution: Optional[ForexExecution] = None,
        trade: Optional[ForexTrade] = None,
    ) -> ForexTrade:
        if trade is None:
            if order is None or execution is None:
                raise ValueError("order and execution are required when creating a trade.")

            trade = ForexTrade(
                trade_id=str(uuid.uuid4()),
                order_id=order.order_id,
                tenant_id=order.tenant_id,
                user_id=order.user_id,
                portfolio_id=order.portfolio_id,
                account_id=order.account_id,
                position_id=None,
                pair=order.pair,
                side=order.side,
                units=execution.units,
                entry_price=execution.price,
                stop_price=order.stop_price,
                target_price=order.target_price,
                realized_pnl=0.0,
                unrealized_pnl=0.0,
                broker=order.broker,
                status="OPEN",
                opened_at=execution.executed_at,
                raw={"order": order.to_dict(), "execution": execution.to_dict()},
            )

        if self.db is not None:
            self.ensure_tables()
            self.db.execute(text(
                """
                INSERT INTO forex_trades (
                    trade_id, order_id, tenant_id, user_id, portfolio_id, account_id,
                    position_id, pair, side, units, entry_price, stop_price, target_price,
                    realized_pnl, unrealized_pnl, broker, status, raw_payload, opened_at, closed_at
                )
                VALUES (
                    :trade_id, :order_id, :tenant_id, :user_id, :portfolio_id, :account_id,
                    :position_id, :pair, :side, :units, :entry_price, :stop_price, :target_price,
                    :realized_pnl, :unrealized_pnl, :broker, :status, :raw_payload, :opened_at, :closed_at
                )
                ON CONFLICT (trade_id)
                DO UPDATE SET
                    position_id = EXCLUDED.position_id,
                    realized_pnl = EXCLUDED.realized_pnl,
                    unrealized_pnl = EXCLUDED.unrealized_pnl,
                    status = EXCLUDED.status,
                    raw_payload = EXCLUDED.raw_payload,
                    closed_at = EXCLUDED.closed_at
                """,
                {
                    **trade.to_dict(),
                    "raw_payload": _json(trade.raw or trade.to_dict()),
                    "opened_at": _naive(trade.opened_at),
                    "closed_at": _naive(trade.closed_at),
                },
            ))
            if hasattr(self.db, "commit"):
                self.db.commit()

        return trade

    def record_execution(self, execution: ForexExecution) -> None:
        if self.db is None:
            return

        self.ensure_tables()
        self.db.execute(text(
            """
            INSERT INTO forex_trade_executions (
                execution_id, order_id, trade_id, pair, side, units, price,
                broker, slippage, raw_payload, executed_at
            )
            VALUES (
                :execution_id, :order_id, :trade_id, :pair, :side, :units, :price,
                :broker, :slippage, :raw_payload, :executed_at
            )
            """,
            {
                **execution.to_dict(),
                "raw_payload": _json(execution.raw),
                "executed_at": _naive(execution.executed_at),
            },
        ))
        if hasattr(self.db, "commit"):
            self.db.commit()

    def record_audit_event(
        self,
        *,
        order: Optional[ForexOrder] = None,
        trade: Optional[ForexTrade] = None,
        account_id: Optional[str] = None,
        trade_id: Optional[str] = None,
        event_type: str,
        message: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        if self.db is None:
            return

        self.ensure_tables()
        self.db.execute(text(
            """
            INSERT INTO forex_trade_audit_log (
                tenant_id, user_id, portfolio_id, account_id, order_id, trade_id,
                event_type, message, payload, created_at
            )
            VALUES (
                :tenant_id, :user_id, :portfolio_id, :account_id, :order_id, :trade_id,
                :event_type, :message, :payload, :created_at
            )
            """,
            {
                "tenant_id": self.tenant_id,
                "user_id": self.user_id,
                "portfolio_id": self.portfolio_id,
                "account_id": account_id or (order.account_id if order else None),
                "order_id": order.order_id if order else None,
                "trade_id": trade.trade_id if trade else trade_id,
                "event_type": event_type,
                "message": message,
                "payload": _json(payload or {
                    "order": order.to_dict() if order else None,
                    "trade": trade.to_dict() if trade else None,
                }),
                "created_at": _naive(_utc_now()),
            },
        ))
        if hasattr(self.db, "commit"):
            self.db.commit()

    def get_order(self, order_id: str) -> Optional[ForexOrder]:
        if self.db is None:
            return None

        row = self.db.execute(text(
            """
            SELECT *
            FROM forex_orders
            WHERE tenant_id = :tenant_id
              AND order_id = :order_id
            LIMIT 1
            """),
            {"tenant_id": self.tenant_id, "order_id": order_id},
        ).fetchone()

        return self._order_from_row(row) if row else None

    def list_orders(self, account_id: Optional[str] = None, status: str = "ALL", limit: int = 100) -> List[ForexOrder]:
        if self.db is None:
            return []

        params = {"tenant_id": self.tenant_id, "limit": int(limit)}
        where = "tenant_id = :tenant_id"

        if account_id:
            where += " AND account_id = :account_id"
            params["account_id"] = account_id

        if status != "ALL":
            where += " AND status = :status"
            params["status"] = status

        rows = self.db.execute(text(
            f"""
            SELECT *
            FROM forex_orders
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT :limit
            """),
            params,
        ).fetchall()

        return [self._order_from_row(row) for row in rows]

    def get_trade(self, trade_id: str) -> Optional[ForexTrade]:
        if self.db is None:
            return None

        row = self.db.execute(text(
            """
            SELECT *
            FROM forex_trades
            WHERE tenant_id = :tenant_id
              AND trade_id = :trade_id
            LIMIT 1
            """),
            {"tenant_id": self.tenant_id, "trade_id": trade_id},
        ).fetchone()

        return self._trade_from_row(row) if row else None

    def list_trades(self, account_id: Optional[str] = None, status: str = "ALL", limit: int = 100) -> List[ForexTrade]:
        if self.db is None:
            return []

        params = {"tenant_id": self.tenant_id, "limit": int(limit)}
        where = "tenant_id = :tenant_id"

        if account_id:
            where += " AND account_id = :account_id"
            params["account_id"] = account_id

        if status != "ALL":
            where += " AND status = :status"
            params["status"] = status

        rows = self.db.execute(text(
            f"""
            SELECT *
            FROM forex_trades
            WHERE {where}
            ORDER BY opened_at DESC
            LIMIT :limit
            """),
            params,
        ).fetchall()

        return [self._trade_from_row(row) for row in rows]

    def _order_from_row(self, row: Any) -> ForexOrder:
        def g(name: str, default: Any = None) -> Any:
            return getattr(row, name, default)

        return ForexOrder(
            order_id=g("order_id"),
            tenant_id=g("tenant_id"),
            user_id=g("user_id"),
            portfolio_id=g("portfolio_id"),
            account_id=g("account_id"),
            pair=g("pair"),
            side=g("side"),
            order_type=g("order_type"),
            units=_safe_float(g("units")),
            status=g("status"),
            tif=g("tif") or DEFAULT_TIF,
            broker=g("broker") or DEFAULT_BROKER,
            limit_price=g("limit_price"),
            stop_price=g("stop_price"),
            target_price=g("target_price"),
            trailing_amount=g("trailing_amount"),
            avg_fill_price=g("avg_fill_price"),
            filled_units=_safe_float(g("filled_units")),
            remaining_units=_safe_float(g("remaining_units")),
            estimated_slippage=_safe_float(g("estimated_slippage")),
            actual_slippage=_safe_float(g("actual_slippage")),
            signal_id=g("signal_id"),
            recommendation=g("recommendation"),
            confidence=g("confidence"),
            composite_score=g("composite_score"),
            rejection_reason=g("rejection_reason"),
            created_at=(g("created_at") or _utc_now()).replace(tzinfo=timezone.utc),
            updated_at=(g("updated_at") or _utc_now()).replace(tzinfo=timezone.utc),
            submitted_at=g("submitted_at").replace(tzinfo=timezone.utc) if g("submitted_at") else None,
            filled_at=g("filled_at").replace(tzinfo=timezone.utc) if g("filled_at") else None,
            cancelled_at=g("cancelled_at").replace(tzinfo=timezone.utc) if g("cancelled_at") else None,
            raw=g("raw_payload"),
        )

    def _trade_from_row(self, row: Any) -> ForexTrade:
        def g(name: str, default: Any = None) -> Any:
            return getattr(row, name, default)

        return ForexTrade(
            trade_id=g("trade_id"),
            order_id=g("order_id"),
            tenant_id=g("tenant_id"),
            user_id=g("user_id"),
            portfolio_id=g("portfolio_id"),
            account_id=g("account_id"),
            position_id=g("position_id"),
            pair=g("pair"),
            side=g("side"),
            units=_safe_float(g("units")),
            entry_price=_safe_float(g("entry_price")),
            stop_price=g("stop_price"),
            target_price=g("target_price"),
            realized_pnl=_safe_float(g("realized_pnl")),
            unrealized_pnl=_safe_float(g("unrealized_pnl")),
            broker=g("broker") or DEFAULT_BROKER,
            status=g("status") or "OPEN",
            opened_at=(g("opened_at") or _utc_now()).replace(tzinfo=timezone.utc),
            closed_at=g("closed_at").replace(tzinfo=timezone.utc) if g("closed_at") else None,
            raw=g("raw_payload"),
        )


def get_forex_trading_engine(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    forex_service: Optional[ForexService] = None,
    forex_ai_engine: Optional[ForexAIEngine] = None,
    forex_portfolio_engine: Optional[ForexPortfolioEngine] = None,
    broker: str = DEFAULT_BROKER,
) -> ForexTradingEngine:
    return ForexTradingEngine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
        forex_service=forex_service,
        forex_ai_engine=forex_ai_engine,
        forex_portfolio_engine=forex_portfolio_engine,
        broker=broker,
    )


def submit_forex_order(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    account_id: str,
    pair: str,
    side: str,
    order_type: str,
    units: float,
    limit_price: Optional[float] = None,
    stop_price: Optional[float] = None,
    target_price: Optional[float] = None,
) -> Dict[str, Any]:
    engine = get_forex_trading_engine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )
    return engine.submit_order(
        account_id=account_id,
        pair=pair,
        side=side,
        order_type=order_type,
        units=units,
        limit_price=limit_price,
        stop_price=stop_price,
        target_price=target_price,
    ).to_dict()