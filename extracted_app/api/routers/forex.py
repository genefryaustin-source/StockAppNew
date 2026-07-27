"""
api/routers/forex.py

Forex Router

REST endpoints under /api/v1/forex for quotes, supported pairs,
portfolio CRUD, order submission/lookup/cancel, positions, and
position lifecycle management (close/reverse/modify/flatten). No
business logic lives here -- see:

    api.services.forex_market_data_api_service
    api.services.forex_portfolios_api_service
    api.services.forex_orders_api_service
    api.services.forex_position_management_api_service

and the underlying modules.forex.* engines each of those wraps.

Route registration order matters in two places below: "/portfolios/
statistics" is registered before "/portfolios/{portfolio_id}" (a GET
on the same path depth), and "/quotes/{pair:path}" uses FastAPI's greedy
path converter -- both call this out explicitly at the point it matters.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.auth.models import AuthenticatedUser
from api.auth.permissions import require_permission
from api.auth.module_entitlements import require_module

from api.exceptions import NotFound
from api.responses import ResponseBuilder

from api.services.module_registry import get_module_registry

from api.schemas.forex_orders import ForexOrderCreateRequest
from api.schemas.forex_portfolios import ForexPortfolioCreateRequest, ForexPortfolioUpdateRequest
from api.schemas.forex_positions import (
    ForexPositionCloseRequest,
    ForexPositionModifyRequest,
    ForexFlattenRequest,
)


router = APIRouter(
    prefix="/api/v1/forex",
    tags=["Forex"],
)


# ==========================================================
# Market data (not tenant-scoped)
# ==========================================================

@router.get("/quotes/{pair:path}")
async def get_forex_quote(
    pair: str,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("forex.read")),
):
    """
    Current quote for a currency pair. Accepts either 'EUR/USD' or
    'EURUSD' -- the slash form works because this path uses FastAPI's
    :path converter (a plain {pair} parameter would stop at the '/'
    and 404). Check the "source"/"provider" fields -- "synthetic_fallback"
    means this is a static placeholder, not a live market quote.
    """
    service = registry.forex_market_data()

    data = service.get_quote(pair=pair)

    return ResponseBuilder.success(request=request, data=data)


@router.get("/pairs")
async def get_forex_pairs(
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("forex.read")),
):
    """Every currency pair this platform supports."""

    service = registry.forex_market_data()

    data = service.get_pairs()

    return ResponseBuilder.success(request=request, data=data)


# ==========================================================
# Portfolios
# ==========================================================
# A forex "portfolio" is a named container
# (modules.forex.forex_portfolio_crud_engine); each one gets its own,
# genuinely isolated trading account/positions the first time an order
# references it (modules.forex.forex_portfolio_engine.
# get_or_create_account). Orders/positions/position-management
# endpoints below all accept an optional portfolio_id and default to
# your default portfolio (auto-created on first use) when omitted.

@router.post("/portfolios", status_code=201)
async def create_forex_portfolio(
    payload: ForexPortfolioCreateRequest,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("forex.write")),
):
    """Create a new forex portfolio."""

    service = registry.forex_portfolios()

    portfolio = service.create_portfolio(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        name=payload.name,
        description=payload.description,
        base_currency=payload.base_currency,
        starting_balance=payload.starting_balance,
        is_default=payload.is_default,
    )

    if portfolio is None:
        from api.exceptions import BadRequest
        raise BadRequest("Unable to create forex portfolio due to a database error.")

    return ResponseBuilder.created(request=request, data=portfolio)


@router.get("/portfolios")
async def list_forex_portfolios(
    request: Request,
    include_archived: bool = False,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("forex.read")),
):
    """Every forex portfolio for the caller (tenant + user)."""

    service = registry.forex_portfolios()

    data = service.list_portfolios(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        include_archived=include_archived,
    )

    return ResponseBuilder.success(request=request, data=data)


@router.get("/portfolios/statistics")
async def get_forex_portfolio_statistics(
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("forex.read")),
):
    """
    Aggregate stats across every portfolio for the caller. Registered
    before "/portfolios/{portfolio_id}" below -- both are GET at the
    same path depth, and FastAPI matches routes in registration order,
    so this must come first or "statistics" would be captured as a
    portfolio_id instead.
    """
    service = registry.forex_portfolios()

    data = service.portfolio_statistics(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
    )

    return ResponseBuilder.success(request=request, data=data)


@router.get("/portfolios/{portfolio_id}")
async def get_forex_portfolio(
    portfolio_id: str,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("forex.read")),
):
    """Single forex portfolio by id, scoped to the caller's tenant."""

    service = registry.forex_portfolios()

    portfolio = service.get_portfolio(tenant_id=current_user.tenant_id, portfolio_id=portfolio_id)

    if portfolio is None:
        raise NotFound("Forex portfolio not found.")

    return ResponseBuilder.success(request=request, data=portfolio)


@router.put("/portfolios/{portfolio_id}")
async def update_forex_portfolio(
    portfolio_id: str,
    payload: ForexPortfolioUpdateRequest,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("forex.write")),
):
    """Update a forex portfolio's name/description/currency/status."""

    service = registry.forex_portfolios()

    portfolio = service.update_portfolio(
        tenant_id=current_user.tenant_id,
        portfolio_id=portfolio_id,
        name=payload.name,
        description=payload.description,
        base_currency=payload.base_currency,
        status=payload.status,
    )

    if portfolio is None:
        raise NotFound("Forex portfolio not found.")

    return ResponseBuilder.success(request=request, data=portfolio)


@router.delete("/portfolios/{portfolio_id}")
async def delete_forex_portfolio(
    portfolio_id: str,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("forex.write")),
):
    """
    Permanently delete a forex portfolio. This removes the portfolio
    record itself, not any trading account/positions already created
    under it -- those remain, just no longer linked to a listed
    portfolio. Consider archive instead if you want it hidden but
    recoverable.
    """
    service = registry.forex_portfolios()

    ok = service.delete_portfolio(tenant_id=current_user.tenant_id, portfolio_id=portfolio_id)

    if not ok:
        raise NotFound("Forex portfolio not found.")

    return ResponseBuilder.success(request=request, data={"id": portfolio_id, "deleted": True})


@router.post("/portfolios/{portfolio_id}/archive")
async def archive_forex_portfolio(
    portfolio_id: str,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("forex.write")),
):
    """Archive a forex portfolio (hidden from default listings, not deleted)."""

    service = registry.forex_portfolios()

    portfolio = service.archive_portfolio(tenant_id=current_user.tenant_id, portfolio_id=portfolio_id)

    if portfolio is None:
        raise NotFound("Forex portfolio not found.")

    return ResponseBuilder.success(request=request, data=portfolio)


@router.post("/portfolios/{portfolio_id}/restore")
async def restore_forex_portfolio(
    portfolio_id: str,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("forex.write")),
):
    """Restore an archived forex portfolio to active status."""

    service = registry.forex_portfolios()

    portfolio = service.restore_portfolio(tenant_id=current_user.tenant_id, portfolio_id=portfolio_id)

    if portfolio is None:
        raise NotFound("Forex portfolio not found.")

    return ResponseBuilder.success(request=request, data=portfolio)


@router.post("/portfolios/{portfolio_id}/set-default")
async def set_default_forex_portfolio(
    portfolio_id: str,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("forex.write")),
):
    """Make this the caller's default portfolio -- used whenever an order/position call omits portfolio_id."""

    service = registry.forex_portfolios()

    portfolio = service.set_default_portfolio(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        portfolio_id=portfolio_id,
    )

    if portfolio is None:
        raise NotFound("Forex portfolio not found.")

    return ResponseBuilder.success(request=request, data=portfolio)


# ==========================================================
# Orders
# ==========================================================

@router.post("/orders", status_code=201)
async def create_forex_order(
    payload: ForexOrderCreateRequest,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("forex.write")),
    _module_check: AuthenticatedUser = Depends(require_module("forex")),
):
    """
    Submit a new forex order. The response is an execution result, not
    a bare order record -- check its "status" field (FILLED, PENDING,
    REJECTED, ERROR) for the outcome, not the HTTP status; a rejected
    order is still a 201, since a valid request was processed and
    produced a real outcome. A MARKET order typically fills
    immediately; LIMIT/STOP orders commonly stay PENDING until
    cancelled or the market reaches the trigger price. Omit
    portfolio_id to use your default portfolio.
    """
    service = registry.forex_orders()

    result = service.create_order(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        pair=payload.pair,
        side=payload.side,
        units=payload.units,
        lots=payload.lots,
        order_type=payload.order_type,
        limit_price=payload.limit_price,
        stop_price=payload.stop_price,
        target_price=payload.target_price,
        leverage=payload.leverage,
        broker=payload.broker,
        portfolio_id=payload.portfolio_id,
    )

    return ResponseBuilder.created(request=request, data=result)


@router.get("/orders/{order_id}")
async def get_forex_order(
    order_id: str,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("forex.read")),
):
    """Single forex order by its broker order id, scoped to the caller's tenant."""

    service = registry.forex_orders()

    order = service.get_order(
        tenant_id=current_user.tenant_id,
        order_id=order_id,
    )

    if order is None:
        raise NotFound("Forex order not found.")

    return ResponseBuilder.success(request=request, data=order)


@router.post("/orders/{order_id}/cancel")
async def cancel_forex_order(
    order_id: str,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("forex.write")),
):
    """Cancel a pending forex order."""

    service = registry.forex_orders()

    result = service.cancel_order(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        order_id=order_id,
    )

    if result is None:
        raise NotFound("Forex order not found.")

    return ResponseBuilder.success(request=request, data=result)


# ==========================================================
# Positions -- read
# ==========================================================

@router.get("/positions")
async def get_forex_positions(
    request: Request,
    status: str = "OPEN",
    portfolio_id: str | None = None,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("forex.read")),
):
    """
    Forex positions for a portfolio. status='ALL' includes closed
    positions. Omit portfolio_id to use your default portfolio.
    """
    service = registry.forex_orders()

    data = service.get_positions(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        status=status,
        portfolio_id=portfolio_id,
    )

    return ResponseBuilder.success(request=request, data=data)


# ==========================================================
# Positions -- lifecycle management
# ==========================================================
# close/reverse/modify(stop-target)/flatten only -- scale_in/scale_out
# are not exposed; see api.services.forex_position_management_api_service's
# module docstring for why.

@router.post("/positions/flatten")
async def flatten_forex_account(
    payload: ForexFlattenRequest,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("forex.write")),
):
    """
    Close every open position in a portfolio's account. Registered
    before "/positions/{position_id}/..." below only as a matter of
    reading order -- there's no actual routing ambiguity here (this is
    POST at a different path depth than those), but grouping the
    account-wide action first makes the position-specific ones below
    easier to scan.
    """
    service = registry.forex_position_management()

    data = service.flatten_account(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        portfolio_id=payload.portfolio_id,
    )

    return ResponseBuilder.success(request=request, data=data)


@router.post("/positions/{position_id}/close")
async def close_forex_position(
    position_id: str,
    payload: ForexPositionCloseRequest,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("forex.write")),
):
    """Close a position, fully or partially."""

    service = registry.forex_position_management()

    result = service.close_position(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        position_id=position_id,
        quantity=payload.quantity,
        exit_price=payload.exit_price,
    )

    if result is None:
        raise NotFound("Forex position not found.")

    return ResponseBuilder.success(request=request, data=result)


@router.post("/positions/{position_id}/reverse")
async def reverse_forex_position(
    position_id: str,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("forex.write")),
):
    """Close a position and immediately open the opposite side."""

    service = registry.forex_position_management()

    result = service.reverse_position(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        position_id=position_id,
    )

    if result is None:
        raise NotFound("Forex position not found.")

    return ResponseBuilder.success(request=request, data=result)


@router.put("/positions/{position_id}")
async def modify_forex_position(
    position_id: str,
    payload: ForexPositionModifyRequest,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("forex.write")),
):
    """Update stop-loss/take-profit on an open position. Omitted fields are left unchanged."""

    service = registry.forex_position_management()

    result = service.modify_position(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        position_id=position_id,
        stop_price=payload.stop_price,
        target_price=payload.target_price,
    )

    if result is None:
        raise NotFound("Forex position not found.")

    return ResponseBuilder.success(request=request, data=result)