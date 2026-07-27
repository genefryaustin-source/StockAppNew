"""
api/routers/portfolio.py

Portfolio Router

REST endpoints under /api/v1/portfolio for CRUD (list/get/create/update/
soft-delete) plus every portfolio-scoped report: positions, orders,
transactions, performance, allocation, history, holdings, analytics,
risk, recommendations, attribution, optimization, benchmark, scenarios,
factors, correlation, rebalance, cash, income, health, and a composite
dashboard.

Each endpoint is a thin wrapper: pull the right service from the module
registry, call it with tenant_id from the authenticated user (never a
client-supplied value) and portfolio_id from the path, and return either
ResponseBuilder.success(...) or raise NotFound(...) -- no business logic
lives in this file.
"""

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Request
from fastapi import Response

from fastapi import Depends, HTTPException





from api.auth.permissions import require_permission
from api.auth.models import AuthenticatedUser

from api.exceptions import NotFound, BadRequest, Conflict

from api.responses import ResponseBuilder
from api.schemas.common import ApiResponse
from api.serializers.order import (
    serialize_order,
    serialize_orders,
)

from api.services.registry import module_registry

from api.serializers.position import (
    serialize_position,
    serialize_positions,
)

from api.serializers.transaction import (
    serialize_transaction,
    serialize_transactions,
)
from api.serializers.performance import (
    serialize_performance,
)
from api.serializers.allocation import (
    serialize_allocation,
)

from api.serializers.history import (
    serialize_history,
)
from api.serializers.holdings import (
    serialize_holdings,
)

from api.serializers.analytics import (
    serialize_analytics,
)
from api.serializers.risk import serialize_risk

from api.services.module_registry import (
    module_registry,
    get_module_registry,
)
from api.schemas.common import ApiResponse
from api.schemas.portfolio import (
    PortfolioCreateRequest,
    PortfolioUpdateRequest,
)


router = APIRouter(

    prefix="/api/v1/portfolio",

    tags=["Portfolio"],

)

@router.get("")
async def list_portfolios(

    request: Request,

    user_id: str | None = None,

    registry = Depends(
        get_module_registry,
    ),

    current_user: AuthenticatedUser = Depends(require_permission("portfolio.read")),

):
    """
    Portfolios belonging to the caller, every portfolio in the tenant
    (for an admin, when no user_id is given or when it's their own),
    or a specific other user's portfolios (for an admin, via ?user_id=).

    A "client"-role caller always defaults to their own user_id --
    omitting the parameter lists only portfolios they own. An admin
    (tenant_admin or super_admin) gets tenant-wide results whether they
    omit the parameter or pass their own id -- an admin's own ownership
    isn't a meaningful narrowing scope the way it is for a client, so
    typing in your own id behaves the same as leaving the field blank.
    This also means portfolios created before ownership tracking
    existed (user_id is NULL) remain visible to any admin without
    needing individual reassignment.

    A non-admin explicitly passing a different user_id is rejected
    (400) rather than silently ignored or silently scoped to their own
    id anyway, so a client relying on this parameter finds out
    immediately if it isn't being honored, instead of getting a
    quietly-different result set than requested.
    """
    from api.serializers.portfolio import serialize_portfolios

    is_admin = current_user.is_super_admin or "tenant_admin" in (current_user.roles or [])

    if user_id is not None and user_id != current_user.user_id:
        # Explicitly looking up a DIFFERENT user's portfolios.
        if not is_admin:
            raise BadRequest(
                "Only an administrator can list another user's portfolios.",
            )
        effective_user_id = user_id
    elif is_admin:
        # No user_id given, or an admin passed their OWN id -- either
        # way, tenant-wide, not scoped to just what they personally
        # created. An admin's own id isn't a meaningful narrowing
        # filter the way it is for a client, so passing it explicitly
        # behaves the same as omitting it.
        effective_user_id = None
    else:
        effective_user_id = current_user.user_id

    portfolio_service = registry.portfolio()

    portfolios = portfolio_service.list_portfolios(
        tenant_id=current_user.tenant_id,
        user_id=effective_user_id,
    )

    return ResponseBuilder.success(
        request=request,
        data=serialize_portfolios(portfolios),
    )
@router.get("/{portfolio_id}")
async def get_portfolio(

    portfolio_id: str,

    request: Request,

    registry = Depends(
        get_module_registry,
    ),

    current_user: AuthenticatedUser = Depends(require_permission("portfolio.read")),

):
    from api.serializers.portfolio import serialize_portfolio

    portfolio_service = registry.portfolio()

    portfolio = portfolio_service.get_portfolio(
        tenant_id=current_user.tenant_id,
        portfolio_id=portfolio_id,
    )

    if portfolio is None:
        raise NotFound("Portfolio not found.")

    return ResponseBuilder.success(
        request=request,
        data=serialize_portfolio(portfolio),
    )

@router.get("/{portfolio_id}/positions")
async def get_portfolio_positions(

    portfolio_id: str,

    request: Request,

    registry=Depends(
        get_module_registry,
    ),

    current_user: AuthenticatedUser = Depends(require_permission("positions.read")),

):

    position_service = registry.positions()

    positions = position_service.list_positions(
        tenant_id=current_user.tenant_id,
        portfolio_id=portfolio_id,
    )

    return ResponseBuilder.success(
        request=request,
        data=serialize_positions(positions),
    )
@router.get("/{portfolio_id}/orders")
async def get_portfolio_orders(

    portfolio_id: str,

    request: Request,

    registry=Depends(get_module_registry),

    current_user: AuthenticatedUser = Depends(require_permission("orders.read")),

):

    order_service = registry.orders()

    orders = order_service.list_orders(

        tenant_id=current_user.tenant_id,

        portfolio_id=portfolio_id,

    )

    return ResponseBuilder.success(

        request=request,

        data=serialize_orders(orders),

    )
@router.get("/{portfolio_id}/transactions")
async def get_portfolio_transactions(

    portfolio_id: str,

    request: Request,

    registry=Depends(get_module_registry),

    current_user: AuthenticatedUser = Depends(require_permission("portfolio.read")),

):

    accounting = registry.accounting()

    transactions = accounting.list_transactions(

        tenant_id=current_user.tenant_id,

        portfolio_id=portfolio_id,

    )

    return ResponseBuilder.success(

        request=request,

        data=serialize_transactions(transactions),

    )

@router.get("/{portfolio_id}/performance")
async def get_portfolio_performance(

    portfolio_id: str,

    request: Request,

    registry=Depends(get_module_registry),

    current_user: AuthenticatedUser = Depends(require_permission("portfolio.read")),

):

    performance = registry.performance()

    report = performance.get_performance(

        tenant_id=current_user.tenant_id,

        portfolio_id=portfolio_id,

    )

    if report is None:

        raise NotFound("Portfolio not found.")

    return ResponseBuilder.success(

        request=request,

        data=serialize_performance(report),

    )


@router.get("/{portfolio_id}/performance-dashboard")
async def get_portfolio_performance_dashboard(

    portfolio_id: str,

    request: Request,

    benchmark: str | None = None,

    period: str = "6mo",

    registry=Depends(get_module_registry),

    current_user: AuthenticatedUser = Depends(require_permission("portfolio.read")),

):
    """
    Mobile-first performance dashboard: snapshot + daily P&L + a
    time-weighted-return approximation, real risk-adjusted metrics
    (Sharpe, Sortino, max drawdown, VaR), benchmark comparison with
    beta and alpha, win rate/profit factor, allocation, top holdings,
    and income -- combined into one response. See
    api.services.portfolio_performance_dashboard_api_service's module
    docstring for exactly which existing service backs each section,
    and any known coverage limits.
    """
    service = registry.performance_dashboard()

    report = service.get_performance_dashboard(
        tenant_id=current_user.tenant_id,
        portfolio_id=portfolio_id,
        benchmark=benchmark,
        period=period,
    )

    if report is None:
        raise NotFound("Portfolio not found.")

    return ResponseBuilder.success(request=request, data=report)


@router.get("/{portfolio_id}/allocation")
async def get_portfolio_allocation(

    portfolio_id: str,

    request: Request,

    registry=Depends(get_module_registry),

    current_user: AuthenticatedUser = Depends(require_permission("portfolio.read")),

):

    allocation_service = registry.allocation()

    report = allocation_service.get_allocation(

        tenant_id=current_user.tenant_id,

        portfolio_id=portfolio_id,

    )

    if report is None:

        raise NotFound("Portfolio not found.")

    return ResponseBuilder.success(

        request=request,

        data=serialize_allocation(report),

    )

@router.get("/{portfolio_id}/history")
async def get_portfolio_history(

    portfolio_id: str,

    request: Request,

    period: str | None = None,

    registry=Depends(get_module_registry),

    current_user: AuthenticatedUser = Depends(require_permission("portfolio.read")),

):
    """
    Equity curve history. period: "1d", "5d", "1mo", "3mo", "6mo",
    "1y", "ytd", or omitted/"max" for full history.
    """
    history_service = registry.history()

    history = history_service.get_history(

        tenant_id=current_user.tenant_id,

        portfolio_id=portfolio_id,

        period=period,

    )

    if history is None:

        raise NotFound("Portfolio not found.")

    return ResponseBuilder.success(

        request=request,

        data=serialize_history(history),

    )
@router.get("/{portfolio_id}/holdings")
async def get_portfolio_holdings(

    portfolio_id: str,

    request: Request,

    registry=Depends(get_module_registry),

    current_user: AuthenticatedUser = Depends(require_permission("portfolio.read")),

):

    service = registry.holdings()

    report = service.get_holdings(

        tenant_id=current_user.tenant_id,

        portfolio_id=portfolio_id,

    )

    if report is None:

        raise NotFound("Portfolio not found.")

    return ResponseBuilder.success(

        request=request,

        data=serialize_holdings(report),

    )

@router.get("/{portfolio_id}/analytics")
async def get_portfolio_analytics(

    portfolio_id: str,

    request: Request,

    registry=Depends(get_module_registry),

    current_user: AuthenticatedUser = Depends(require_permission("analytics.read")),

):

    service = registry.analytics()

    report = service.get_analytics(

        tenant_id=current_user.tenant_id,

        portfolio_id=portfolio_id,

    )

    if report is None:

        raise NotFound("Portfolio not found.")

    return ResponseBuilder.success(

        request=request,

        data=serialize_analytics(report),

    )
@router.get("/{portfolio_id}/risk")
async def get_portfolio_risk(

    portfolio_id: str,

    request: Request,

    registry=Depends(get_module_registry),

    current_user: AuthenticatedUser = Depends(require_permission("analytics.read")),

):

    service = registry.portfolio_risk()

    report = service.get_portfolio_risk(

        tenant_id=current_user.tenant_id,

        portfolio_id=portfolio_id,

    )

    if report is None:

        raise NotFound("Portfolio not found.")

    return ResponseBuilder.success(

        request=request,

        data=serialize_risk(report),

    )

@router.get(
    "/{portfolio_id}/recommendations",
    response_model=ApiResponse,
)
async def get_portfolio_recommendations(

    portfolio_id: str,

    request: Request,

    registry = Depends(
        get_module_registry,
    ),

    current_user: AuthenticatedUser = Depends(require_permission("recommendations.read")),

):

    service = registry.portfolio_recommendations()

    report = service.get_recommendations(

        tenant_id=current_user.tenant_id,

        portfolio_id=portfolio_id,

    )

    if report is None:

        raise NotFound("Portfolio not found.")

    return ResponseBuilder.success(

        request=request,

        data=report,

    )

@router.get(
    "/{portfolio_id}/attribution",
    response_model=ApiResponse,
)
async def get_portfolio_attribution(

    portfolio_id: str,

    request: Request,

    registry=Depends(
        get_module_registry,
    ),

    current_user: AuthenticatedUser = Depends(require_permission("analytics.read")),

):

    service = registry.portfolio_attribution()

    report = service.get_attribution(

        tenant_id=current_user.tenant_id,

        portfolio_id=portfolio_id,

    )

    if report is None:

        raise NotFound("Portfolio not found.")

    return ResponseBuilder.success(

        request=request,

        data=report,

    )
@router.get(
    "/{portfolio_id}/attribution/analytics",
    response_model=ApiResponse,
)
async def get_portfolio_attribution_analytics(

    portfolio_id: str,

    request: Request,

    registry=Depends(
        get_module_registry,
    ),

    current_user: AuthenticatedUser = Depends(require_permission("analytics.read")),

):

    service = registry.portfolio_attribution_analytics()

    report = service.get_analytics(

        tenant_id=current_user.tenant_id,

        portfolio_id=portfolio_id,

    )

    if report is None:

        raise NotFound("Portfolio not found.")

    return ResponseBuilder.success(

        request=request,

        data=report,

    )


# ==========================================================
# CREATE / UPDATE / DELETE
# ==========================================================

@router.post("", status_code=201)
async def create_portfolio(
    payload: PortfolioCreateRequest,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("portfolio.write")),
):
    """
    Create a new portfolio for the authenticated user's tenant.

    Returns 201 with the created portfolio, or 400 if creation fails
    (e.g. a database error mid-insert).
    """
    from api.serializers.portfolio import serialize_portfolio

    portfolio_service = registry.portfolio()

    result = portfolio_service.create_portfolio(
        tenant_id=current_user.tenant_id,
        name=payload.name,
        description=payload.description,
        benchmark=payload.benchmark,
        base_currency=payload.base_currency,
        starting_cash=payload.starting_cash,
    )

    if result is None:
        raise BadRequest("Unable to create portfolio.")

    portfolio = portfolio_service.get_portfolio(
        tenant_id=current_user.tenant_id,
        portfolio_id=result["id"],
    )

    return ResponseBuilder.created(
        request=request,
        data=serialize_portfolio(portfolio),
    )


@router.put("/{portfolio_id}")
async def update_portfolio(
    portfolio_id: str,
    payload: PortfolioUpdateRequest,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("portfolio.write")),
):
    """
    Partial update of a portfolio's name/description/benchmark/
    base_currency, and (admin-only) its owning user_id.

    starting_cash and is_active are not editable here -- see
    PortfolioService.update_portfolio for why.
    """
    from api.serializers.portfolio import serialize_portfolio
    from api.auth.permissions import has_permission

    if payload.user_id is not None and not (current_user.is_super_admin or has_permission(current_user, "admin.tenants")):
        raise BadRequest(
            "Only an administrator can assign portfolio ownership.",
        )

    portfolio_service = registry.portfolio()

    portfolio = portfolio_service.update_portfolio(
        tenant_id=current_user.tenant_id,
        portfolio_id=portfolio_id,
        name=payload.name,
        description=payload.description,
        benchmark=payload.benchmark,
        base_currency=payload.base_currency,
        user_id=payload.user_id,
    )

    if portfolio is None:
        raise NotFound("Portfolio not found.")

    return ResponseBuilder.success(
        request=request,
        data=serialize_portfolio(portfolio),
    )


@router.delete("/{portfolio_id}")
async def delete_portfolio(
    portfolio_id: str,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("portfolio.write")),
):
    """
    Soft delete: marks the portfolio inactive. Does not destroy trading
    history -- see PortfolioService.deactivate_portfolio.
    """

    portfolio_service = registry.portfolio()

    ok = portfolio_service.deactivate_portfolio(
        tenant_id=current_user.tenant_id,
        portfolio_id=portfolio_id,
    )

    if not ok:
        raise NotFound("Portfolio not found.")

    return ResponseBuilder.success(
        request=request,
        data={"id": portfolio_id, "is_active": False},
    )


# ==========================================================
# OPTIMIZATION / BENCHMARK / SCENARIOS / FACTORS / CORRELATION
# ==========================================================

@router.get("/{portfolio_id}/optimization")
async def get_portfolio_optimization(
    portfolio_id: str,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("analytics.read")),
):
    """
    Risk Parity and Black-Litterman suggested weights for currently-
    held symbols, alongside current market-value weights.
    """
    service = registry.portfolio_optimization()

    report = service.get_optimization(
        tenant_id=current_user.tenant_id,
        portfolio_id=portfolio_id,
    )

    if report is None:
        raise NotFound("Portfolio not found.")

    return ResponseBuilder.success(request=request, data=report)


@router.get("/{portfolio_id}/benchmark")
async def get_portfolio_benchmark(
    portfolio_id: str,
    request: Request,
    benchmark: str | None = None,
    period: str = "6mo",
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("analytics.read")),
):
    """
    Cumulative portfolio return vs. a benchmark (defaults to the
    portfolio's own configured benchmark, or SPY) over `period`
    (e.g. "1mo", "6mo", "1y").
    """
    service = registry.portfolio_benchmark()

    report = service.get_benchmark(
        tenant_id=current_user.tenant_id,
        portfolio_id=portfolio_id,
        benchmark=benchmark,
        period=period,
    )

    if report is None:
        raise NotFound("Portfolio not found.")

    return ResponseBuilder.success(request=request, data=report)


@router.get("/{portfolio_id}/scenarios")
async def get_portfolio_scenarios(
    portfolio_id: str,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("analytics.read")),
):
    """
    Estimated P&L impact of a wider set of market-shock scenarios
    (-20% to +15%) than the brief default embedded in /risk.
    """
    service = registry.portfolio_scenarios()

    report = service.get_scenarios(
        tenant_id=current_user.tenant_id,
        portfolio_id=portfolio_id,
    )

    if report is None:
        raise NotFound("Portfolio not found.")

    return ResponseBuilder.success(request=request, data=report)


@router.get("/{portfolio_id}/factors")
async def get_portfolio_factors(
    portfolio_id: str,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("analytics.read")),
):
    """
    Real market-beta exposure (CAPM, via regression) for each position
    and the portfolio overall, against the portfolio's benchmark.
    """
    service = registry.portfolio_factors()

    report = service.get_factors(
        tenant_id=current_user.tenant_id,
        portfolio_id=portfolio_id,
    )

    if report is None:
        raise NotFound("Portfolio not found.")

    return ResponseBuilder.success(request=request, data=report)


@router.get("/{portfolio_id}/correlation")
async def get_portfolio_correlation(
    portfolio_id: str,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("analytics.read")),
):
    """
    Pairwise correlation matrix across currently-held symbols, from
    real daily return series.
    """
    service = registry.portfolio_correlation()

    report = service.get_correlation(
        tenant_id=current_user.tenant_id,
        portfolio_id=portfolio_id,
    )

    if report is None:
        raise NotFound("Portfolio not found.")

    return ResponseBuilder.success(request=request, data=report)


# ==========================================================
# REBALANCE / CASH / INCOME
# ==========================================================

@router.get("/{portfolio_id}/rebalance")
async def get_portfolio_rebalance(
    portfolio_id: str,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("analytics.read")),
):
    """
    Trades needed to move current holdings to an equal weight across
    currently-held symbols (the default target -- no personalized
    allocation is stored on a Portfolio today).
    """
    service = registry.portfolio_rebalance()

    report = service.get_rebalance(
        tenant_id=current_user.tenant_id,
        portfolio_id=portfolio_id,
    )

    if report is None:
        raise NotFound("Portfolio not found.")

    return ResponseBuilder.success(request=request, data=report)


@router.get("/{portfolio_id}/cash")
async def get_portfolio_cash(
    portfolio_id: str,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("portfolio.read")),
):
    """
    Current cash balance and the most recent cash-ledger entries.
    """
    service = registry.portfolio_cash()

    report = service.get_cash(
        tenant_id=current_user.tenant_id,
        portfolio_id=portfolio_id,
    )

    if report is None:
        raise NotFound("Portfolio not found.")

    return ResponseBuilder.success(request=request, data=report)


@router.get("/{portfolio_id}/income")
async def get_portfolio_income(
    portfolio_id: str,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("portfolio.read")),
):
    """
    Non-trade cash income (dividends, interest, and similar). Honestly
    empty today -- no dividend/interest capture mechanism exists yet.
    """
    service = registry.portfolio_income()

    report = service.get_income(
        tenant_id=current_user.tenant_id,
        portfolio_id=portfolio_id,
    )

    if report is None:
        raise NotFound("Portfolio not found.")

    return ResponseBuilder.success(request=request, data=report)


# ==========================================================
# HEALTH / DASHBOARD
# ==========================================================

@router.get("/{portfolio_id}/health")
async def get_portfolio_health(
    portfolio_id: str,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("analytics.read")),
):
    """
    Fast health check: overall status (healthy/warning/critical),
    active limit breaches, and headline risk numbers. Lighter than
    the full /risk report -- meant to answer "is this portfolio OK"
    quickly.
    """
    service = registry.portfolio_health()

    report = service.get_health(
        tenant_id=current_user.tenant_id,
        portfolio_id=portfolio_id,
    )

    if report is None:
        raise NotFound("Portfolio not found.")

    return ResponseBuilder.success(request=request, data=report)


@router.get("/{portfolio_id}/dashboard")
async def get_portfolio_dashboard(
    portfolio_id: str,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("portfolio.read")),
):
    """
    Composite {portfolio, performance, allocation, cash, health}
    payload in one call, for an overview screen. A failing section
    reports why rather than failing the whole request.
    """
    service = registry.portfolio_dashboard()

    report = service.get_dashboard(
        tenant_id=current_user.tenant_id,
        portfolio_id=portfolio_id,
    )

    if report is None:
        raise NotFound("Portfolio not found.")

    return ResponseBuilder.success(request=request, data=report)

# ==========================================================
# RECOMMENDATIONS SUB-RESOURCES
# ==========================================================
# Each of these wraps a real, already-built engine in
# modules/trading_intelligence/ -- lifecycle state, performance, target
# tracking, stop-loss monitoring, unified alerts, and the full
# command-center snapshot. No business logic lives in this file; see
# each api.services.portfolio_recommendations_*_api_service module.

@router.get("/{portfolio_id}/recommendations/lifecycle")
async def get_portfolio_recommendations_lifecycle(
    portfolio_id: str,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("recommendations.read")),
):
    """
    Recommendation lifecycle summary, funnel metrics (counts at each
    stage from OPEN through closed/expired), and per-recommendation
    lifecycle detail.
    """
    service = registry.portfolio_recommendations_lifecycle()

    report = service.get_lifecycle(
        tenant_id=current_user.tenant_id,
        portfolio_id=portfolio_id,
    )

    if report is None:
        raise NotFound("Portfolio not found.")

    return ResponseBuilder.success(request=request, data=report)


@router.get("/{portfolio_id}/recommendations/performance")
async def get_portfolio_recommendations_performance(
    portfolio_id: str,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("recommendations.read")),
):
    """
    Recommendation performance: win rate, execution rate, and realized
    P&L, broken down by recommendation type, conviction, signal, and
    sector.
    """
    service = registry.portfolio_recommendations_performance()

    report = service.get_performance(
        tenant_id=current_user.tenant_id,
        portfolio_id=portfolio_id,
    )

    if report is None:
        raise NotFound("Portfolio not found.")

    return ResponseBuilder.success(request=request, data=report)


@router.get("/{portfolio_id}/recommendations/targets")
async def get_portfolio_recommendations_targets(
    portfolio_id: str,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("recommendations.read")),
):
    """
    Target-price tracking on open recommendation-driven positions:
    progress to target, distance remaining, active target alerts, and
    target hits.
    """
    service = registry.portfolio_recommendations_targets()

    report = service.get_targets(
        tenant_id=current_user.tenant_id,
        portfolio_id=portfolio_id,
    )

    if report is None:
        raise NotFound("Portfolio not found.")

    return ResponseBuilder.success(request=request, data=report)


@router.get("/{portfolio_id}/recommendations/stops")
async def get_portfolio_recommendations_stops(
    portfolio_id: str,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("recommendations.read")),
):
    """
    Stop-loss monitoring on open recommendation-driven positions:
    distance to stop, risk dollars remaining, active stop alerts, and
    stop breaches.
    """
    service = registry.portfolio_recommendations_stops()

    report = service.get_stops(
        tenant_id=current_user.tenant_id,
        portfolio_id=portfolio_id,
    )

    if report is None:
        raise NotFound("Portfolio not found.")

    return ResponseBuilder.success(request=request, data=report)


@router.get("/{portfolio_id}/recommendations/alerts")
async def get_portfolio_recommendations_alerts(
    portfolio_id: str,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("recommendations.read")),
):
    """
    Unified recommendation alert feed -- target, stop, trade-management,
    portfolio-risk, and lifecycle alerts combined, deduplicated, and
    sorted by severity -- plus alert counts.
    """
    service = registry.portfolio_recommendations_alerts()

    report = service.get_alerts(
        tenant_id=current_user.tenant_id,
        portfolio_id=portfolio_id,
    )

    if report is None:
        raise NotFound("Portfolio not found.")

    return ResponseBuilder.success(request=request, data=report)


@router.get("/{portfolio_id}/recommendations/command-center")
async def get_portfolio_recommendations_command_center(
    portfolio_id: str,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("recommendations.read")),
):
    """
    Full recommendation command-center snapshot: lifecycle, targets,
    stops, alerts, performance, attribution, and portfolio risk
    together, plus a derived 0-100 health score. The heaviest of the
    recommendations endpoints -- touches every underlying engine.
    """
    service = registry.portfolio_recommendations_command_center()

    report = service.get_command_center(
        tenant_id=current_user.tenant_id,
        portfolio_id=portfolio_id,
    )

    if report is None:
        raise NotFound("Portfolio not found.")

    return ResponseBuilder.success(request=request, data=report)

# ==========================================================
# REPORTS
# ==========================================================

@router.get("/{portfolio_id}/reports/pdf")
async def get_portfolio_pdf_report(
    portfolio_id: str,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("portfolio.read")),
):
    """
    A generated PDF report for one portfolio: cover page, NAV chart
    (when there's price history to chart), and an executive summary
    table (total/annualized return, equity, unrealized P&L).

    Returns the raw PDF bytes with Content-Type: application/pdf,
    unlike every other endpoint in this router -- there's no JSON
    envelope here, since the response body IS the deliverable.
    """
    service = registry.portfolio_reports()

    pdf_bytes = service.generate_pdf(
        tenant_id=current_user.tenant_id,
        portfolio_id=portfolio_id,
    )

    if pdf_bytes is None:
        raise NotFound("Portfolio not found, or the report could not be generated.")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="portfolio_{portfolio_id}_report.pdf"',
        },
    )