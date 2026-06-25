from __future__ import annotations

import json
import logging
import math
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from modules.forex.forex_service import ForexService, get_forex_service, normalize_pair
    from modules.forex.forex_portfolio_engine import ForexPortfolioEngine, get_forex_portfolio_engine
    from modules.forex.forex_trading_engine import ForexTradingEngine, get_forex_trading_engine
except Exception:
    from forex_service import ForexService, get_forex_service, normalize_pair
    from forex_portfolio_engine import ForexPortfolioEngine, get_forex_portfolio_engine
    from forex_trading_engine import ForexTradingEngine, get_forex_trading_engine

logger = logging.getLogger(__name__)


@dataclass
class ForexTradeManagementAlert:
    alert_id: str
    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]
    account_id: str
    position_id: str
    pair: str
    alert_type: str
    severity: str
    message: str
    current_price: float
    stop_price: Optional[float]
    target_price: Optional[float]
    unrealized_pnl: float
    created_at: datetime
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _naive(dt: datetime) -> datetime:
    return dt.replace(tzinfo=None)


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
    try:
        return json.loads(json.dumps(value, default=str))
    except Exception:
        return {"value": str(value)}


class ForexTradeManagementEngine:
    """
    Forex stop/target monitoring, alerts, trailing stops, and position lifecycle management.
    """

    def __init__(
        self,
        *,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        db: Any = None,
        forex_service: Optional[ForexService] = None,
        forex_portfolio_engine: Optional[ForexPortfolioEngine] = None,
        forex_trading_engine: Optional[ForexTradingEngine] = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.portfolio_id = portfolio_id
        self.db = db
        self.forex_service = forex_service or get_forex_service(tenant_id=tenant_id, user_id=user_id, db=db)
        self.forex_portfolio_engine = forex_portfolio_engine or get_forex_portfolio_engine(
            tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id, db=db, forex_service=self.forex_service
        )
        self.forex_trading_engine = forex_trading_engine or get_forex_trading_engine(
            tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id, db=db,
            forex_service=self.forex_service, forex_portfolio_engine=self.forex_portfolio_engine
        )

    def ensure_tables(self) -> None:
        if self.db is None:
            return
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS forex_trade_management_alerts (
                alert_id VARCHAR(80) PRIMARY KEY,
                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),
                account_id VARCHAR(80),
                position_id VARCHAR(80),
                pair VARCHAR(20),
                alert_type VARCHAR(80),
                severity VARCHAR(40),
                message TEXT,
                current_price DOUBLE PRECISION,
                stop_price DOUBLE PRECISION,
                target_price DOUBLE PRECISION,
                unrealized_pnl DOUBLE PRECISION,
                raw_payload JSONB,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS forex_trade_management_events (
                id SERIAL PRIMARY KEY,
                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),
                account_id VARCHAR(80),
                position_id VARCHAR(80),
                event_type VARCHAR(80),
                message TEXT,
                payload JSONB,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)
        if hasattr(self.db, "commit"):
            self.db.commit()

    def monitor_positions(
        self,
        *,
        account_id: str,
        auto_close: bool = False,
    ) -> List[ForexTradeManagementAlert]:
        positions = self.forex_portfolio_engine.refresh_positions(account_id=account_id)
        alerts: List[ForexTradeManagementAlert] = []

        for position in positions:
            current_price = _safe_float(position.current_price)
            alert = None

            if position.stop_price is not None:
                stop_hit = current_price <= position.stop_price if position.side == "LONG" else current_price >= position.stop_price
                if stop_hit:
                    alert = self._build_alert(position, "STOP_HIT", "HIGH", "Stop price reached.")

            if alert is None and position.target_price is not None:
                target_hit = current_price >= position.target_price if position.side == "LONG" else current_price <= position.target_price
                if target_hit:
                    alert = self._build_alert(position, "TARGET_HIT", "MEDIUM", "Target price reached.")

            if alert is None and position.unrealized_pnl < 0:
                notional = max(_safe_float(position.notional_value), 1.0)
                drawdown = abs(position.unrealized_pnl) / notional
                if drawdown >= 0.03:
                    alert = self._build_alert(position, "DRAWDOWN_WARNING", "MEDIUM", "Position drawdown exceeds 3% of notional.")

            if alert:
                alerts.append(alert)
                self.save_alert(alert)
                if auto_close and alert.alert_type in {"STOP_HIT", "TARGET_HIT"}:
                    try:
                        self.forex_trading_engine.close_position(position.id)
                        self.record_event(
                            account_id=position.account_id,
                            position_id=position.id,
                            event_type="AUTO_CLOSE",
                            message=f"Auto-closed {position.pair} after {alert.alert_type}.",
                            payload=alert.to_dict(),
                        )
                    except Exception as exc:
                        logger.warning("Auto-close failed for %s: %s", position.id, exc)

        return alerts

    def apply_trailing_stop(
        self,
        *,
        position_id: str,
        trailing_pct: float = 0.01,
    ) -> Optional[Dict[str, Any]]:
        position = self.forex_portfolio_engine.get_position(position_id=position_id)
        if not position:
            return None

        quote = self.forex_service.get_quote(position.pair)
        current_price = _safe_float(quote.price)
        trail = abs(current_price * trailing_pct)

        if position.side == "LONG":
            new_stop = current_price - trail
            if position.stop_price is None or new_stop > position.stop_price:
                position.stop_price = new_stop
        else:
            new_stop = current_price + trail
            if position.stop_price is None or new_stop < position.stop_price:
                position.stop_price = new_stop

        position.current_price = current_price
        position.updated_at = _utc_now()
        self.forex_portfolio_engine._persist_position(position)
        self.record_event(
            account_id=position.account_id,
            position_id=position.id,
            event_type="TRAILING_STOP_UPDATED",
            message=f"Trailing stop updated for {position.pair}.",
            payload=position.to_dict(),
        )
        return position.to_dict()

    def _build_alert(self, position: Any, alert_type: str, severity: str, message: str) -> ForexTradeManagementAlert:
        return ForexTradeManagementAlert(
            alert_id=str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,
            account_id=position.account_id,
            position_id=position.id,
            pair=position.pair,
            alert_type=alert_type,
            severity=severity,
            message=message,
            current_price=_safe_float(position.current_price),
            stop_price=position.stop_price,
            target_price=position.target_price,
            unrealized_pnl=_safe_float(position.unrealized_pnl),
            created_at=_utc_now(),
            raw=position.to_dict(),
        )

    def save_alert(self, alert: ForexTradeManagementAlert) -> None:
        if self.db is None:
            return
        self.ensure_tables()
        self.db.execute("""
            INSERT INTO forex_trade_management_alerts (
                alert_id, tenant_id, user_id, portfolio_id, account_id, position_id,
                pair, alert_type, severity, message, current_price, stop_price,
                target_price, unrealized_pnl, raw_payload, created_at
            )
            VALUES (
                :alert_id, :tenant_id, :user_id, :portfolio_id, :account_id, :position_id,
                :pair, :alert_type, :severity, :message, :current_price, :stop_price,
                :target_price, :unrealized_pnl, :raw_payload, :created_at
            )
            ON CONFLICT (alert_id) DO NOTHING
        """, {**alert.to_dict(), "raw_payload": _json(alert.raw), "created_at": _naive(alert.created_at)})
        if hasattr(self.db, "commit"):
            self.db.commit()

    def record_event(self, *, account_id: str, position_id: Optional[str], event_type: str, message: str, payload: Optional[Dict[str, Any]] = None) -> None:
        if self.db is None:
            return
        self.ensure_tables()
        self.db.execute("""
            INSERT INTO forex_trade_management_events (
                tenant_id, user_id, portfolio_id, account_id, position_id, event_type, message, payload, created_at
            )
            VALUES (
                :tenant_id, :user_id, :portfolio_id, :account_id, :position_id, :event_type, :message, :payload, :created_at
            )
        """, {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "portfolio_id": self.portfolio_id,
            "account_id": account_id,
            "position_id": position_id,
            "event_type": event_type,
            "message": message,
            "payload": _json(payload),
            "created_at": _naive(_utc_now()),
        })
        if hasattr(self.db, "commit"):
            self.db.commit()

    def load_alerts(self, limit: int = 100) -> List[Dict[str, Any]]:
        if self.db is None:
            return []
        self.ensure_tables()
        rows = self.db.execute("""
            SELECT * FROM forex_trade_management_alerts
            WHERE tenant_id = :tenant_id
            ORDER BY created_at DESC
            LIMIT :limit
        """, {"tenant_id": self.tenant_id, "limit": int(limit)}).fetchall()
        return [
            {
                "alert_id": getattr(row, "alert_id", None),
                "account_id": getattr(row, "account_id", None),
                "position_id": getattr(row, "position_id", None),
                "pair": getattr(row, "pair", None),
                "alert_type": getattr(row, "alert_type", None),
                "severity": getattr(row, "severity", None),
                "message": getattr(row, "message", None),
                "current_price": getattr(row, "current_price", None),
                "unrealized_pnl": getattr(row, "unrealized_pnl", None),
                "created_at": str(getattr(row, "created_at", "")),
            }
            for row in rows
        ]


def get_forex_trade_management_engine(**kwargs: Any) -> ForexTradeManagementEngine:
    return ForexTradeManagementEngine(**kwargs)
