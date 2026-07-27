"""
api/routers/crypto.py

Crypto Router

REST endpoints under /api/v1/crypto for market data, order
submission/lookup/cancel, and positions. No business logic lives
here -- see api.services.crypto_orders_api_service and
api.services.crypto_market_data_api_service.

get_order/cancel_order are asset-class-agnostic already (TradeOrder
lookup/cancellation by tenant ownership doesn't care about symbol
format), so those two endpoints delegate to the existing, already-
tested api.services.orders_api_service.OrdersAPIService rather than
duplicate it -- the same service GET/POST /api/v1/orders/{id} use.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.auth.models import AuthenticatedUser
from api.auth.permissions import require_permission
from api.auth.module_entitlements import require_module

from api.exceptions import NotFound
from api.responses import ResponseBuilder

from api.services.module_registry import get_module_registry

from api.schemas.crypto_orders import CryptoOrderCreateRequest


router = APIRouter(
    prefix="/api/v1/crypto",
    tags=["Crypto"],
)


# ==========================================================
# Market data (not tenant-scoped) -- real CoinGecko/Alternative.me
# data, free, no API key required.
# ==========================================================

@router.get("/coins")
async def get_crypto_top_coins(
    request: Request,
    limit: int = 100,
    category: str | None = None,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("crypto.read")),
):
    """Top coins by market cap."""

    service = registry.crypto_market_data()

    data = service.get_top_coins(limit=limit, category=category)

    return ResponseBuilder.success(request=request, data=data)


@router.get("/global")
async def get_crypto_global_stats(
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("crypto.read")),
):
    """
    Global crypto market stats. Registered before "/coins/{coin_id}"
    below only as a matter of reading order -- there's no actual
    routing ambiguity here (a different top-level path), but grouping
    the platform-wide endpoints together makes this easier to scan.
    """
    service = registry.crypto_market_data()

    data = service.get_global_stats()

    return ResponseBuilder.success(request=request, data=data)


@router.get("/trending")
async def get_crypto_trending(
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("crypto.read")),
):
    """Currently trending coins."""

    service = registry.crypto_market_data()

    data = service.get_trending()

    return ResponseBuilder.success(request=request, data=data)


@router.get("/fear-greed")
async def get_crypto_fear_greed(
    request: Request,
    limit: int = 30,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("crypto.read")),
):
    """Fear & Greed index history."""

    service = registry.crypto_market_data()

    data = service.get_fear_greed(limit=limit)

    return ResponseBuilder.success(request=request, data=data)


@router.get("/search")
async def search_crypto_coin(
    request: Request,
    query: str,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("crypto.read")),
):
    """Search for a coin by name or symbol -- use the returned id with GET /coins/{id}."""

    service = registry.crypto_market_data()

    data = service.search_coin(query=query)

    return ResponseBuilder.success(request=request, data=data)


@router.get("/coins/{coin_id}")
async def get_crypto_coin_detail(
    coin_id: str,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("crypto.read")),
):
    """
    Full detail for a single coin by its CoinGecko id (e.g. "bitcoin",
    not "BTC") -- use GET /search or GET /coins to find a coin's id.
    """
    service = registry.crypto_market_data()

    data = service.get_coin_detail(coin_id=coin_id)

    return ResponseBuilder.success(request=request, data=data)


# ==========================================================
# Orders
# ==========================================================

@router.post("/orders", status_code=201)
async def create_crypto_order(
    payload: CryptoOrderCreateRequest,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("crypto.write")),
    _module_check: AuthenticatedUser = Depends(require_module("crypto")),
):
    """
    Submit a crypto order through the same canonical execution path
    stocks use (modules.stocks.stock_trading_service.
    StockTradingService), just with a crypto-appropriate broker: real
    exchange execution via ccxt if this tenant has it enabled and
    configured (Admin > Brokers), otherwise simulated paper fills --
    the same default every other asset class uses.

    The response is an execution result, not a bare order record --
    check its "success"/"status" fields for the outcome, not the HTTP
    status; a rejected order (e.g. an unrecognized symbol format) is
    still a 201, since a valid request was processed and produced a
    real outcome.
    """
    service = registry.crypto_orders()

    result = service.create_order(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        portfolio_id=payload.portfolio_id,
        symbol=payload.symbol,
        side=payload.side,
        qty=payload.qty,
        order_type=payload.order_type,
        tif=payload.tif,
        limit_price=payload.limit_price,
        stop_price=payload.stop_price,
    )

    if result is None:
        raise NotFound("Portfolio not found.")

    return ResponseBuilder.created(request=request, data=result)


@router.get("/orders/{order_id}")
async def get_crypto_order(
    order_id: int,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("crypto.read")),
):
    """
    Single order by id. Orders are asset-class-agnostic once created
    (TradeOrder doesn't distinguish crypto from stock orders), so this
    delegates to the same order lookup GET /api/v1/orders/{id} uses.
    """
    service = registry.orders_api()

    order = service.get_order(tenant_id=current_user.tenant_id, order_id=order_id)

    if order is None:
        raise NotFound("Order not found.")

    return ResponseBuilder.success(request=request, data=order)


@router.post("/orders/{order_id}/cancel")
async def cancel_crypto_order(
    order_id: int,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("crypto.write")),
):
    """Cancel a pending order. Delegates to the same cancellation logic GET/POST /api/v1/orders use."""

    service = registry.orders_api()

    result = service.cancel_order(tenant_id=current_user.tenant_id, order_id=order_id)

    if result is None:
        raise NotFound("Order not found.")

    return ResponseBuilder.success(request=request, data=result)


# ==========================================================
# Positions
# ==========================================================

@router.get("/positions")
async def get_crypto_positions(
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("crypto.read")),
):
    """
    Every open crypto position across every portfolio this tenant
    has, identified by ccxt-unified pair symbols (e.g. "BTC/USDT") --
    crypto and stock positions share the same portfolio_positions
    table, distinguished only by symbol format.
    """
    service = registry.crypto_orders()

    data = service.get_positions(tenant_id=current_user.tenant_id)

    return ResponseBuilder.success(request=request, data=data)