"""
api/routers/orders.py

Orders Router

REST endpoints under /api/v1/orders: submit, fetch, cancel, and replace
stock orders. No business logic lives here -- see
api.services.orders_api_service.OrdersAPIService and
modules.stocks.stock_trading_service.StockTradingService.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.auth.permissions import require_permission
from api.auth.module_entitlements import require_module
from api.auth.models import AuthenticatedUser

from api.exceptions import NotFound
from api.responses import ResponseBuilder

from api.schemas.orders import OrderCreateRequest, OrderReplaceRequest

from api.services.module_registry import get_module_registry


router = APIRouter(
    prefix="/api/v1/orders",
    tags=["Trading"],
)


@router.post("", status_code=201)
async def create_order(
    payload: OrderCreateRequest,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("orders.write")),
    _module_check: AuthenticatedUser = Depends(require_module("stocks")),
):
    """
    Submit a new stock order. The response is an ExecutionResult, not a
    bare order record -- check its "success" field for whether the
    order actually executed; a rejected order (invalid symbol,
    insufficient shares to sell, etc.) is still a 201, since a valid
    request was processed and produced a real outcome.
    """
    service = registry.orders_api()

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
        recommendation_id=payload.recommendation_id,
    )

    if result is None:
        raise NotFound("Portfolio not found.")

    return ResponseBuilder.created(request=request, data=result)


@router.get("/{order_id}")
async def get_order(
    order_id: int,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("orders.read")),
):
    """Single order by id, scoped to the authenticated user's tenant."""
    service = registry.orders_api()

    order = service.get_order(
        tenant_id=current_user.tenant_id,
        order_id=order_id,
    )

    if order is None:
        raise NotFound("Order not found.")

    return ResponseBuilder.success(request=request, data=order)


@router.delete("/{order_id}")
async def delete_order(
    order_id: int,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("orders.write")),
):
    """
    Cancel an order (REST-conventional alias for POST .../cancel --
    same underlying action). See OrdersAPIService.cancel_order for why
    this currently always reports the order as already filled.
    """
    service = registry.orders_api()

    result = service.cancel_order(
        tenant_id=current_user.tenant_id,
        order_id=order_id,
    )

    if result is None:
        raise NotFound("Order not found.")

    return ResponseBuilder.success(request=request, data=result)


@router.post("/{order_id}/cancel")
async def cancel_order(
    order_id: int,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("orders.write")),
):
    """
    Cancel an order. See OrdersAPIService.cancel_order for why this
    currently always reports the order as already filled -- the paper
    broker fills every order synchronously, so there's no pending state
    to cancel yet.
    """
    service = registry.orders_api()

    result = service.cancel_order(
        tenant_id=current_user.tenant_id,
        order_id=order_id,
    )

    if result is None:
        raise NotFound("Order not found.")

    return ResponseBuilder.success(request=request, data=result)


@router.post("/{order_id}/replace")
async def replace_order(
    order_id: int,
    payload: OrderReplaceRequest,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("orders.write")),
):
    """
    Replace (modify) an order's qty/limit_price/stop_price. See
    OrdersAPIService.replace_order for why this currently always
    reports the order as already filled.
    """
    service = registry.orders_api()

    result = service.replace_order(
        tenant_id=current_user.tenant_id,
        order_id=order_id,
        qty=payload.qty,
        limit_price=payload.limit_price,
        stop_price=payload.stop_price,
    )

    if result is None:
        raise NotFound("Order not found.")

    return ResponseBuilder.success(request=request, data=result)