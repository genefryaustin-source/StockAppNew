"""
api/routers/tenant_export.py

Tenant Full Export Router

REST endpoint under /api/v1/tenant for a single, complete data export:
everything available for a tenant (and every user in it) across every
asset class -- stocks, options, crypto, tokenized real-world assets, and
forex. Positions, full snapshot/equity history, and full order history in
one call.

Distinct from GET /api/v1/executive/mobile-dashboard, which returns
tenant-wide counts and rollups for rendering a UI screen -- this is a
data export, not a dashboard summary.

Tenant-wide, cross-user by design, so this requires an admin role
(tenant_admin or super_admin) rather than the plain portfolio.read
permission a client already has for their own portfolios -- see
list_portfolios in portfolio.py for the same reasoning applied there.

Registered under a distinct top-level prefix (/api/v1/tenant, not
/api/v1/portfolio) specifically so its literal path can never collide
with portfolio.py's /api/v1/portfolio/{portfolio_id} pattern regardless
of router include order.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from api.auth.models import AuthenticatedUser
from api.auth.current_user import get_current_user
from api.exceptions import Forbidden
from api.responses import ResponseBuilder
from api.services.module_registry import get_module_registry

router = APIRouter(
    prefix="/api/v1/tenant",
    tags=["Tenant Export"],
)


@router.get("/portfolio/full")
async def get_tenant_full_portfolio(
    request: Request,
    include_all_users: bool = Query(
        default=True,
        description="Include every user's data for this tenant (admin only). "
                    "Only a super admin/tenant admin may call this endpoint at all.",
    ),
    snapshot_limit_per_portfolio: int = Query(default=500, ge=1, le=5000),
    order_limit_per_portfolio: int = Query(default=500, ge=1, le=5000),
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Complete tenant portfolio export: tenant info, all tenant users, all
    portfolios, unified cross-asset positions (stocks/options/crypto/
    tokenized real-world assets/forex), full equity/drawdown history,
    full snapshot history, and full order history (stocks+crypto+
    tokenized-RWA share one order table; options and forex each have
    their own and are reported separately).

    Requires an admin role (tenant_admin or super_admin) -- this
    endpoint is inherently cross-user by design, unlike every other
    portfolio.read-gated endpoint in this API which is scoped to the
    caller's own data (or explicitly opted into via ?user_id= with the
    same admin check). A non-admin caller gets 403, not a silently
    empty or self-only response, so it's obvious this endpoint isn't
    the right one for a client-role integration.

    Each section reports {"available": false, "reason": ...} in its own
    place if it fails, rather than failing the whole export.
    """
    is_admin = current_user.is_super_admin or "tenant_admin" in (current_user.roles or [])
    if not is_admin:
        raise Forbidden(
            "This endpoint requires an administrator role (tenant_admin or super_admin) -- "
            "it returns data across every user in the tenant, not just the caller's own.",
        )

    service = registry.portfolio_full_export()

    data = service.get_full_export(
        tenant_id=current_user.tenant_id,
        include_all_users=include_all_users,
        snapshot_limit_per_portfolio=snapshot_limit_per_portfolio,
        order_limit_per_portfolio=order_limit_per_portfolio,
    )

    return ResponseBuilder.success(request=request, data=data)
