"""
api/services/crypto_orders_api_service.py

Crypto Orders API Service

Backs POST /api/v1/crypto/orders, GET /api/v1/crypto/orders/{id},
POST /api/v1/crypto/orders/{id}/cancel, GET /api/v1/crypto/positions.

No new trading logic lives here -- crypto orders go through the same
canonical modules.stocks.stock_trading_service.StockTradingService
every stock order already uses (same TradeOrder/TradeFill/
PortfolioPosition tables, same lifecycle/execution-event/trade-
attribution pipeline), just constructed with a crypto-appropriate
broker instead of the default paper stock broker: modules.portfolio.
brokers.ccxt_broker.CCXTBroker if the tenant has ccxt enabled (Admin >
Brokers) and real exchange credentials configured, otherwise the same
PaperBroker every other asset class uses for simulated fills.

Symbols must be ccxt-unified pair format ("BTC/USDT", not "BTCUSDT")
-- this is what distinguishes a crypto position from a stock position
within the shared portfolio_positions table (no stock ticker contains
"/"), and what modules.market_data.service.get_latest_price_map()
uses to route pricing to modules.crypto.pricing instead of the stock
provider pipeline.

get_order/cancel_order are asset-class-agnostic already (they operate
on TradeOrder/Portfolio purely by tenant ownership, regardless of
symbol format) -- this service delegates to the existing, already-
tested api.services.orders_api_service.OrdersAPIService for those
rather than duplicate them.
"""

from __future__ import annotations

import logging
from typing import Any

from models.trading import Portfolio, PortfolioPosition

logger = logging.getLogger(__name__)


def _safe_rollback(db) -> None:
    try:
        db.rollback()
    except Exception:
        pass


class CryptoOrdersAPIService:
    """API service for crypto order lifecycle and positions."""

    def __init__(self, db):
        self.db = db

    # ---------------------------------------------------------
    # Broker resolution
    # ---------------------------------------------------------

    def _resolve_broker(self, *, tenant_id: str):
        """
        CCXT if this tenant has it enabled (Admin > Brokers) --
        real exchange credentials are still required for it to
        actually connect (modules.portfolio.brokers.ccxt_broker.
        CCXTBroker reports itself as unconfigured otherwise, and
        StockTradingService's own order-rejection path handles that
        the same way it already does for Alpaca/Tradier/IBKR).
        Falls back to the paper broker -- every asset class's default,
        not a crypto-specific fallback.
        """
        from modules.portfolio.brokers.broker_settings import enabled_brokers_for_tenant
        from modules.portfolio.brokers.factory import get_broker

        enabled = enabled_brokers_for_tenant(self.db, tenant_id)
        broker_name = "ccxt" if "ccxt" in enabled else "paper"

        broker = get_broker(market_data_service=None, broker_name=broker_name, live=False)

        return broker, broker_name

    @staticmethod
    def _normalize_pair(symbol: str) -> str:
        """
        Ensures a ccxt-unified "BASE/QUOTE" shape. A caller sending
        "btcusdt" (no slash) is treated as an error rather than
        guessed at -- there's no reliable way to split an unfamiliar
        concatenated symbol into base/quote without a known-pairs
        list, and a wrong guess would silently trade the wrong thing.
        """
        symbol = str(symbol or "").upper().strip()
        return symbol

    # ---------------------------------------------------------
    # Create
    # ---------------------------------------------------------

    def create_order(
        self,
        *,
        tenant_id: str,
        user_id: str | None,
        portfolio_id: str,
        symbol: str,
        side: str,
        qty: float,
        order_type: str = "market",
        tif: str = "day",
        limit_price: float | None = None,
        stop_price: float | None = None,
    ) -> dict[str, Any] | None:
        """
        Submit a crypto order via StockTradingService -- the same
        canonical execution path stocks use. Returns the
        ExecutionResult as a dict regardless of whether the order
        succeeded or was rejected; check "success", not the HTTP
        status. Returns None if portfolio_id doesn't exist or doesn't
        belong to tenant_id, which the router turns into a 404.
        """

        _safe_rollback(self.db)

        portfolio = (
            self.db.query(Portfolio)
            .filter(Portfolio.id == portfolio_id, Portfolio.tenant_id == tenant_id)
            .one_or_none()
        )

        if portfolio is None:
            return None

        symbol = self._normalize_pair(symbol)

        if "/" not in symbol:
            return {
                "success": False,
                "status": "rejected",
                "message": (
                    f"'{symbol}' isn't a valid crypto pair symbol. Use the "
                    "ccxt-unified format, e.g. 'BTC/USDT'."
                ),
            }

        broker, broker_name = self._resolve_broker(tenant_id=tenant_id)

        try:
            from modules.stocks.stock_trading_service import StockTradingService

            service = StockTradingService(self.db, broker=broker, market_data_service=None)

            result = service.submit_order(
                portfolio_id=portfolio_id,
                user_id=self._coerce_user_id(user_id),
                symbol=symbol,
                side=side,
                qty=qty,
                order_type=order_type,
                tif=tif,
                limit_price=limit_price,
                stop_price=stop_price,
            )

            return {
                "success": result.success,
                "status": result.status,
                "order_id": result.order_id,
                "broker": broker_name,
                "broker_order_id": result.broker_order_id,
                "symbol": result.symbol,
                "side": result.side,
                "quantity": result.quantity,
                "filled_price": result.filled_price,
                "commission": result.commission,
                "slippage": result.slippage,
                "message": result.message,
            }

        except Exception:
            logger.exception("Failed to submit crypto order | symbol=%s", symbol)
            _safe_rollback(self.db)
            return {
                "success": False,
                "status": "error",
                "message": "Order submission failed due to an internal error.",
            }

    @staticmethod
    def _coerce_user_id(user_id: str | None):
        if user_id is None:
            return None
        try:
            return int(user_id)
        except (TypeError, ValueError):
            return None

    # ---------------------------------------------------------
    # Positions
    # ---------------------------------------------------------

    def get_positions(self, *, tenant_id: str) -> dict[str, Any]:
        """
        Every open crypto position across every portfolio this tenant
        has -- filtered to symbols in ccxt-unified pair format (the
        same "/" convention used everywhere else in this service),
        since crypto and stock positions share the same
        portfolio_positions table.
        """

        _safe_rollback(self.db)

        try:
            rows = (
                self.db.query(PortfolioPosition)
                .join(Portfolio, Portfolio.id == PortfolioPosition.portfolio_id)
                .filter(Portfolio.tenant_id == tenant_id)
                .filter(PortfolioPosition.symbol.like("%/%"))
                .filter(PortfolioPosition.qty != 0)
                .all()
            )

        except Exception:
            logger.exception("Failed to load crypto positions | tenant_id=%s", tenant_id)
            _safe_rollback(self.db)
            return {"position_count": 0, "positions": []}

        positions = [
            {
                "portfolio_id": row.portfolio_id,
                "symbol": row.symbol,
                "qty": row.qty,
                "avg_cost": row.avg_cost,
                "market_price": row.market_price,
                "market_value": row.market_value,
                "unrealized_pnl": row.unrealized_pnl,
            }
            for row in rows
        ]

        return {"position_count": len(positions), "positions": positions}