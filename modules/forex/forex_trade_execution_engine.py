"""
modules/forex/forex_trade_execution_engine.py

Forex Trade Execution Engine

Paper/live-ready execution layer for Forex trading. This module validates,
prices, and executes Forex orders through the Forex price service and portfolio
manager while optionally persisting orders to the database.

The engine is intentionally compatible with the current StockApp pattern:
- paper-first execution
- SQLAlchemy-tolerant persistence
- normalized order result payloads
- risk validation before fill
- integration hooks for future live broker routing
"""

from __future__ import annotations

import uuid
import math
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List
from modules.forex.forex_portfolio_cache import (
    get_forex_portfolio_cache,
)
try:
    from sqlalchemy import text
except Exception:
    text = None

try:
    from modules.forex.forex_price_service import get_forex_price_service
except Exception:
    get_forex_price_service = None

try:
    from modules.forex.forex_portfolio_manager import get_forex_portfolio_manager
except Exception:
    get_forex_portfolio_manager = None


VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"market", "limit", "stop", "stop_limit"}
VALID_TIF = {"day", "gtc", "ioc", "fok"}
DEFAULT_MAX_NOTIONAL = 250000.0
DEFAULT_MAX_RISK_DOLLARS = 1000.0
DEFAULT_SLIPPAGE_BPS = 1.5
DEFAULT_COMMISSION_PER_MILLION = 25.0


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().replace(microsecond=0).isoformat()


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        out = float(value)
        if math.isnan(out) or math.isinf(out):
            return default
        return out
    except Exception:
        return default


def normalize_pair(pair: str) -> str:
    text = str(pair or "").upper().replace("-", "/").replace("_", "/").replace(" ", "")
    if "/" in text:
        left, right = text.split("/", 1)
        return f"{left[:3]}/{right[:3]}"
    if len(text) >= 6:
        return f"{text[:3]}/{text[3:6]}"
    return text


@dataclass
class ForexOrderRequest:
    pair: str
    side: str
    units: float
    order_type: str = "market"
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    tif: str = "day"
    portfolio_id: Optional[str] = None
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    broker: str = "paper"
    notes: Optional[str] = None

    def normalized(self) -> "ForexOrderRequest":
        self.pair = normalize_pair(self.pair)
        self.side = str(self.side or "").upper()
        self.order_type = str(self.order_type or "market").lower()
        self.tif = str(self.tif or "day").lower()
        self.units = abs(float(self.units or 0.0))
        return self


@dataclass
class ForexExecutionResult:
    status: str
    pair: str
    side: str
    order_type: str
    units: float
    broker: str
    broker_order_id: str
    requested_price: Optional[float]
    filled_price: Optional[float]
    filled_units: float
    commission: float
    slippage: float
    notional: float
    provider: Optional[str]
    error: Optional[str]
    created_at: str
    filled_at: Optional[str]
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ForexTradeExecutionEngine:

    def __init__(
        self,
        db=None,
        max_notional: float = DEFAULT_MAX_NOTIONAL,
        max_risk_dollars: float = DEFAULT_MAX_RISK_DOLLARS,
        slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
        commission_per_million: float = DEFAULT_COMMISSION_PER_MILLION,
    ):
        self.db = db
        self.max_notional = float(max_notional)
        self.max_risk_dollars = float(max_risk_dollars)
        self.slippage_bps = float(slippage_bps)
        self.commission_per_million = float(commission_per_million)
        self.price_service = get_forex_price_service() if get_forex_price_service else None
        self.portfolio_manager = (
            get_forex_portfolio_manager(db=db)
            if get_forex_portfolio_manager
            else None
        )
        self.cache = get_forex_portfolio_cache()
    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------

    def ensure_tables(self) -> None:
        if self.db is None or text is None:
            return

        self.db.execute(text("""
            CREATE TABLE IF NOT EXISTS forex_trade_orders (
                id SERIAL PRIMARY KEY,
                broker_order_id VARCHAR(100),
                tenant_id VARCHAR(100),
                portfolio_id VARCHAR(100),
                user_id VARCHAR(100),
                pair VARCHAR(20) NOT NULL,
                side VARCHAR(20) NOT NULL,
                order_type VARCHAR(30),
                tif VARCHAR(20),
                units DOUBLE PRECISION,
                limit_price DOUBLE PRECISION,
                stop_price DOUBLE PRECISION,
                requested_price DOUBLE PRECISION,
                filled_price DOUBLE PRECISION,
                filled_units DOUBLE PRECISION,
                status VARCHAR(50),
                broker VARCHAR(50),
                commission DOUBLE PRECISION,
                slippage DOUBLE PRECISION,
                notional DOUBLE PRECISION,
                provider VARCHAR(100),
                error TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                filled_at TIMESTAMP
            )
        """))
        self.db.commit()

    def persist_execution(
        self,
        request: ForexOrderRequest,
        result: Dict[str, Any],
    ) -> None:
        if self.db is None or text is None:
            return

        self.ensure_tables()

        created = datetime.now(timezone.utc).replace(tzinfo=None)
        filled_at = created if result.get("status") == "filled" else None

        self.db.execute(text("""
            INSERT INTO forex_trade_orders (
                broker_order_id,
                tenant_id,
                portfolio_id,
                user_id,
                pair,
                side,
                order_type,
                tif,
                units,
                limit_price,
                stop_price,
                requested_price,
                filled_price,
                filled_units,
                status,
                broker,
                commission,
                slippage,
                notional,
                provider,
                error,
                notes,
                created_at,
                filled_at
            )
            VALUES (
                :broker_order_id,
                :tenant_id,
                :portfolio_id,
                :user_id,
                :pair,
                :side,
                :order_type,
                :tif,
                :units,
                :limit_price,
                :stop_price,
                :requested_price,
                :filled_price,
                :filled_units,
                :status,
                :broker,
                :commission,
                :slippage,
                :notional,
                :provider,
                :error,
                :notes,
                :created_at,
                :filled_at
            )
        """), {
            "broker_order_id": result.get("broker_order_id"),
            "tenant_id": request.tenant_id,
            "portfolio_id": request.portfolio_id,
            "user_id": request.user_id,
            "pair": request.pair,
            "side": request.side,
            "order_type": request.order_type,
            "tif": request.tif,
            "units": request.units,
            "limit_price": request.limit_price,
            "stop_price": request.stop_price,
            "requested_price": result.get("requested_price"),
            "filled_price": result.get("filled_price"),
            "filled_units": result.get("filled_units"),
            "status": result.get("status"),
            "broker": result.get("broker"),
            "commission": result.get("commission"),
            "slippage": result.get("slippage"),
            "notional": result.get("notional"),
            "provider": result.get("provider"),
            "error": result.get("error"),
            "notes": result.get("notes"),
            "created_at": created,
            "filled_at": filled_at,
        })
        self.db.commit()

        print("INVALIDATING PORTFOLIO CACHE")

        self.cache.invalidate_portfolio(
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            portfolio_id=request.portfolio_id,
        )
    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def submit_order(
        self,
        pair: str,
        side: str,
        units: float,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        tif: str = "day",
        portfolio_id: Optional[str] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        broker: str = "paper",
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:

        request = ForexOrderRequest(
            pair=pair,
            side=side,
            units=units,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price,
            tif=tif,
            portfolio_id=portfolio_id,
            user_id=user_id,
            tenant_id=tenant_id,
            broker=broker,
            notes=notes,
        ).normalized()

        validation = self.validate_order(request)
        if not validation["valid"]:
            result = self._rejected_result(request, validation["reason"])
            self.persist_execution(request, result)
            return result

        quote = self._quote(request.pair)
        market_price = safe_float(quote.get("mid") or quote.get("last"))

        if market_price <= 0:
            result = self._rejected_result(request, "No valid market price.")
            result["provider"] = quote.get("provider")
            self.persist_execution(request, result)
            return result

        trigger = self._order_triggered(request, market_price)
        if not trigger["triggered"]:
            result = self._open_result(request, market_price, trigger["reason"], quote)
            self.persist_execution(request, result)
            return result

        if request.broker.lower() != "paper":
            result = self._rejected_result(
                request,
                "Live Forex broker routing is not enabled yet.",
            )
            self.persist_execution(request, result)
            return result

        result = self._execute_paper_order(request, market_price, quote)
        self.persist_execution(request, result)

        if result["status"] == "filled" and self.portfolio_manager:
            try:
                self.portfolio_manager.save_position(
                    pair=request.pair,
                    side="LONG" if request.side == "BUY" else "SHORT",
                    units=request.units,
                    avg_price=result["filled_price"],
                    portfolio_id=request.portfolio_id,
                    user_id=request.user_id,
                    tenant_id=request.tenant_id,
                )
            except Exception as exc:
                result["notes"] = f"{result.get('notes') or ''} | Position save failed: {exc}".strip(" |")

        return result

    def execute_recommendation(
        self,
        recommendation: Dict[str, Any],
        units: Optional[float] = None,
        portfolio_id: Optional[str] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        pair = recommendation.get("pair")
        rec = str(recommendation.get("recommendation") or recommendation.get("direction") or "").upper()

        if "BUY" in rec:
            side = "BUY"
        elif "SELL" in rec:
            side = "SELL"
        else:
            return {
                "status": "rejected",
                "reason": "Recommendation is not executable.",
                "recommendation": recommendation,
            }

        suggested_notional = safe_float(recommendation.get("suggested_notional"), 0.0)
        entry = safe_float(recommendation.get("entry_price"), 0.0)

        if units is None:
            if suggested_notional > 0 and entry > 0:
                units = suggested_notional / entry
            else:
                units = 10000.0

        return self.submit_order(
            pair=pair,
            side=side,
            units=units,
            order_type="market",
            portfolio_id=portfolio_id,
            user_id=user_id,
            tenant_id=tenant_id,
            broker="paper",
            notes=f"Executed from recommendation: {recommendation.get('rationale','')}",
        )

    def batch_execute_recommendations(
        self,
        recommendations: List[Dict[str, Any]],
        limit: int = 3,
        portfolio_id: Optional[str] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        results = []
        for rec in recommendations[: int(limit)]:
            results.append(
                self.execute_recommendation(
                    rec,
                    portfolio_id=portfolio_id,
                    user_id=user_id,
                    tenant_id=tenant_id,
                )
            )
        return results

    # ------------------------------------------------------------------
    # Validation / pricing
    # ------------------------------------------------------------------

    def validate_order(self, request: ForexOrderRequest) -> Dict[str, Any]:
        if not request.pair or "/" not in request.pair:
            return {"valid": False, "reason": "Valid Forex pair is required."}

        if request.side not in VALID_SIDES:
            return {"valid": False, "reason": f"Side must be one of {sorted(VALID_SIDES)}."}

        if request.order_type not in VALID_ORDER_TYPES:
            return {"valid": False, "reason": f"Order type must be one of {sorted(VALID_ORDER_TYPES)}."}

        if request.tif not in VALID_TIF:
            return {"valid": False, "reason": f"TIF must be one of {sorted(VALID_TIF)}."}

        if request.units <= 0:
            return {"valid": False, "reason": "Units must be greater than zero."}

        if request.order_type in {"limit", "stop_limit"} and not request.limit_price:
            return {"valid": False, "reason": "Limit price is required for limit orders."}

        if request.order_type in {"stop", "stop_limit"} and not request.stop_price:
            return {"valid": False, "reason": "Stop price is required for stop orders."}

        estimated_price = safe_float(request.limit_price or request.stop_price, 1.0)
        estimated_notional = abs(request.units * estimated_price)

        if estimated_notional > self.max_notional:
            return {
                "valid": False,
                "reason": f"Estimated notional {estimated_notional:,.2f} exceeds max {self.max_notional:,.2f}.",
            }

        return {"valid": True, "reason": "OK"}

    def _quote(self, pair: str) -> Dict[str, Any]:
        if not self.price_service:
            return {"pair": pair, "error": "ForexPriceService unavailable."}

        try:
            return self.price_service.get_quote(pair, force_refresh=False)
        except Exception as exc:
            return {"pair": pair, "error": str(exc)}

    def _order_triggered(self, request: ForexOrderRequest, market_price: float) -> Dict[str, Any]:
        if request.order_type == "market":
            return {"triggered": True, "reason": "Market order."}

        if request.order_type == "limit":
            limit = safe_float(request.limit_price)
            if request.side == "BUY" and market_price <= limit:
                return {"triggered": True, "reason": "Buy limit marketable."}
            if request.side == "SELL" and market_price >= limit:
                return {"triggered": True, "reason": "Sell limit marketable."}
            return {"triggered": False, "reason": "Limit order resting."}

        if request.order_type == "stop":
            stop = safe_float(request.stop_price)
            if request.side == "BUY" and market_price >= stop:
                return {"triggered": True, "reason": "Buy stop triggered."}
            if request.side == "SELL" and market_price <= stop:
                return {"triggered": True, "reason": "Sell stop triggered."}
            return {"triggered": False, "reason": "Stop order pending."}

        if request.order_type == "stop_limit":
            stop = safe_float(request.stop_price)
            limit = safe_float(request.limit_price)
            stop_triggered = (
                market_price >= stop if request.side == "BUY" else market_price <= stop
            )
            if not stop_triggered:
                return {"triggered": False, "reason": "Stop-limit stop not triggered."}

            if request.side == "BUY" and market_price <= limit:
                return {"triggered": True, "reason": "Stop-limit buy marketable."}
            if request.side == "SELL" and market_price >= limit:
                return {"triggered": True, "reason": "Stop-limit sell marketable."}
            return {"triggered": False, "reason": "Stop triggered but limit not marketable."}

        return {"triggered": False, "reason": "Unsupported order type."}

    # ------------------------------------------------------------------
    # Result builders
    # ------------------------------------------------------------------

    def _execute_paper_order(
        self,
        request: ForexOrderRequest,
        market_price: float,
        quote: Dict[str, Any],
    ) -> Dict[str, Any]:
        slippage = self._slippage_amount(market_price, request.side)
        filled_price = market_price + slippage if request.side == "BUY" else market_price - slippage
        notional = abs(request.units * filled_price)
        commission = self._commission(notional)

        result = ForexExecutionResult(
            status="filled",
            pair=request.pair,
            side=request.side,
            order_type=request.order_type,
            units=request.units,
            broker=request.broker,
            broker_order_id=f"FX-PAPER-{uuid.uuid4().hex[:12].upper()}",
            requested_price=market_price,
            filled_price=round(filled_price, 6),
            filled_units=request.units,
            commission=round(commission, 4),
            slippage=round(abs(slippage), 6),
            notional=round(notional, 2),
            provider=quote.get("provider"),
            error=None,
            created_at=utc_now_iso(),
            filled_at=utc_now_iso(),
            notes=request.notes,
        ).to_dict()

        return result

    def _rejected_result(self, request: ForexOrderRequest, error: str) -> Dict[str, Any]:
        return ForexExecutionResult(
            status="rejected",
            pair=request.pair,
            side=request.side,
            order_type=request.order_type,
            units=request.units,
            broker=request.broker,
            broker_order_id=f"FX-REJECT-{uuid.uuid4().hex[:12].upper()}",
            requested_price=None,
            filled_price=None,
            filled_units=0.0,
            commission=0.0,
            slippage=0.0,
            notional=0.0,
            provider=None,
            error=error,
            created_at=utc_now_iso(),
            filled_at=None,
            notes=request.notes,
        ).to_dict()

    def _open_result(
        self,
        request: ForexOrderRequest,
        market_price: float,
        reason: str,
        quote: Dict[str, Any],
    ) -> Dict[str, Any]:
        return ForexExecutionResult(
            status="open",
            pair=request.pair,
            side=request.side,
            order_type=request.order_type,
            units=request.units,
            broker=request.broker,
            broker_order_id=f"FX-OPEN-{uuid.uuid4().hex[:12].upper()}",
            requested_price=market_price,
            filled_price=None,
            filled_units=0.0,
            commission=0.0,
            slippage=0.0,
            notional=abs(request.units * market_price),
            provider=quote.get("provider"),
            error=None,
            created_at=utc_now_iso(),
            filled_at=None,
            notes=f"{request.notes or ''} {reason}".strip(),
        ).to_dict()

    def _slippage_amount(self, price: float, side: str) -> float:
        return price * (self.slippage_bps / 10000.0)

    def _commission(self, notional: float) -> float:
        return abs(notional) / 1_000_000.0 * self.commission_per_million


_ENGINE = None


def get_forex_trade_execution_engine(db=None) -> ForexTradeExecutionEngine:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexTradeExecutionEngine(db=db)
    return _ENGINE
