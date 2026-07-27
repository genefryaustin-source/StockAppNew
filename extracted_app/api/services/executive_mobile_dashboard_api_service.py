"""
api/services/executive_mobile_dashboard_api_service.py

Executive Mobile Dashboard API Service

Backs GET /api/v1/executive/mobile-dashboard -- a single, aggregated
payload combining equities, forex, options, crypto, a cross-asset
portfolio rollup, analytics fabric, provider health, and platform
activity, so a mobile client makes one request instead of one per
asset class.

No new business logic lives here -- every section wraps an already-
built, already-tested service:
    equities            -> api.services.executive_dashboard_api_service
                            (the "portfolio" section -- tenant-wide
                            stock portfolio/position counts)
    forex               -> api.services.forex_orders_api_service +
                            api.services.forex_portfolios_api_service
    options             -> api.services.options_orders_api_service
    crypto              -> not built yet; crypto has no trading path
                            at all today, so this is reported as
                            unavailable, not faked
    portfolio           -> a cross-asset rollup computed from the
                            equities/forex/options sections above
    analytics_fabric,
    provider_health,
    platform_activity   -> api.services.executive_dashboard_api_service
                            (the "analytics_fabric"/"providers"/
                            "platform" sections)

Each section is independent: one failing (or not yet existing, like
crypto) never fails the rest of the response, matching
executive_dashboard_api_service's own per-section error handling. A
caller can also request only specific sections via the `sections`
param, so a mobile screen that only needs, say, forex + portfolio
doesn't pay for computing everything else.
"""

from __future__ import annotations

import logging
from typing import Any
from datetime import UTC, datetime
from modules.portfolio.portfolio_service import PortfolioService

from modules.portfolio.portfolio_analytics_service import (
    PortfolioAnalyticsService,
)

from modules.portfolio.portfolio_performance_service import (
    PortfolioPerformanceService,
)
logger = logging.getLogger(__name__)


ALL_SECTIONS = [
    "equities",
    "forex",
    "options",
    "crypto",
    "portfolio",
    "market",
    "analytics_fabric",
    "provider_health",
    "platform_activity",
    "executive_hero",
    "executive_kpis",
    "asset_classes",
    "executive_ai_brief",
]

# Sections backed by api.services.executive_dashboard_api_service's own
# get_summary() output, keyed by (this section's name -> that one's key).
_EXEC_SUMMARY_SECTIONS = {
    "analytics_fabric": "analytics_fabric",
    "provider_health": "providers",
    "platform_activity": "platform",
}


class ExecutiveMobileDashboardAPIService:
    """API service for the aggregated mobile executive dashboard."""

    def __init__(self, db):
        self.db = db

    def get_mobile_dashboard(
        self,
        *,
        tenant_id: str,
        user_id: str | None,
        is_super_admin: bool = False,
        roles: list[str] | None = None,
        sections: list[str] | None = None,
        portfolio_id: str | None = None,
    ) -> dict[str, Any]:

        selected = [s for s in (sections or ALL_SECTIONS) if s in ALL_SECTIONS]

        # The actual security boundary: which asset-class modules this
        # tenant is licensed for, checked here regardless of what the
        # client requested. A client omitting a section it already
        # knows it can't access is a UX nicety; this is what actually
        # prevents a client from getting real data for one it isn't
        # licensed for by asking anyway.
        modules = self._get_tenant_modules(tenant_id, is_super_admin=is_super_admin)

        # Computed once (not once per section) and shared by every
        # section that needs it -- get_summary() itself runs 12
        # sub-queries, so this avoids tripling that work when multiple
        # exec-summary-backed sections are requested together.
        exec_summary = None
        if any(
            s in selected
            for s in (
                "equities", "portfolio", "executive_hero", "executive_kpis",
                "asset_classes", "executive_ai_brief", *_EXEC_SUMMARY_SECTIONS,
            )
        ):
            exec_summary = self._safe_call(
                "executive_summary",
                lambda: self._get_exec_summary(
                    tenant_id=tenant_id, is_super_admin=is_super_admin, roles=roles,
                ),
            )

        result: dict[str, Any] = {}

        # Computed at most once each per request and reused by the
        # portfolio rollup below if both are requested together --
        # these aren't free (each does several real queries), and
        # forex's own auto-create-default-portfolio side effect means
        # calling it twice isn't just wasteful, it can also observe
        # different state the second time. Only computed at all if the
        # module is actually licensed -- an unlicensed module skips the
        # real work entirely rather than compute it and then withhold it.
        forex_section = None
        if modules["forex"] and ("forex" in selected or "portfolio" in selected):
            forex_section = self._safe_call(
                "forex", lambda: self._forex_section(tenant_id=tenant_id, user_id=user_id),
            )

        options_section = None
        if modules["options"] and ("options" in selected or "portfolio" in selected):
            options_section = self._safe_call(
                "options", lambda: self._options_section(tenant_id=tenant_id),
            )

        # Computed for "crypto", "portfolio", and "asset_classes" --
        # this used to be hardcoded to {"available": False} in all
        # three places, written before real crypto trading existed on
        # this platform and never updated afterward. Confirmed as a
        # real, reported bug: a tenant with an actual crypto portfolio
        # and real positions still saw "not yet available" everywhere.
        crypto_section = None
        if modules["crypto"] and ("crypto" in selected or "portfolio" in selected or "asset_classes" in selected):
            crypto_section = self._safe_call(
                "crypto", lambda: self._crypto_section(tenant_id=tenant_id),
            )

        if "equities" in selected:
            result["equities"] = (
                self._safe_call(
                    "equities",
                    lambda: self._equities_section(exec_summary, tenant_id=tenant_id, portfolio_id=portfolio_id),
                )
                if modules["stocks"]
                else self._not_licensed()
            )

        if "market" in selected:
            result["market"] = self._safe_call("market", self._market_section)

        if "forex" in selected:
            result["forex"] = forex_section if modules["forex"] else self._not_licensed()

        if "options" in selected:
            result["options"] = options_section if modules["options"] else self._not_licensed()

        if "crypto" in selected:
            result["crypto"] = (
                crypto_section if modules["crypto"] else self._not_licensed()
            )

        if "portfolio" in selected:
            result["portfolio"] = self._portfolio_rollup(
                modules=modules,
                exec_summary=exec_summary,
                forex_section=forex_section,
                options_section=options_section,
                crypto_section=crypto_section,
            )

        # ---------------------------------------------------------
        # Mobile-specific blended sections (hero / KPIs / asset
        # classes / AI brief). Each only computed if actually
        # requested (added to ALL_SECTIONS like everything else --
        # this used to run unconditionally whenever exec_summary had
        # been computed for any reason, which meant requesting only
        # ?sections=portfolio also silently paid for computing and
        # returned three additional sections nobody asked for).
        # ---------------------------------------------------------

        needs_portfolio_summary = any(
            s in selected
            for s in ("executive_hero", "executive_kpis", "asset_classes")
        )

        portfolio_summary = None
        if needs_portfolio_summary:
            # Gated on modules["stocks"]: this used to run
            # unconditionally whenever any of these three sections was
            # requested, meaning a tenant with stocks disabled still
            # got a real, computed portfolio_value/cash/total_equity/
            # position count through executive_hero/executive_kpis/
            # asset_classes.equities -- confirmed directly, a disabled-
            # stocks tenant's real portfolio count leaked through
            # asset_classes.equities.portfolio_count. Skips the
            # (per-portfolio, multi-query) work entirely when
            # unlicensed, matching how forex/options sections already
            # skip their own work above.
            portfolio_summary = (
                self._mobile_portfolio_summary(tenant_id=tenant_id)
                if modules["stocks"]
                else self._zero_portfolio_summary()
            )

        opportunities = exec_summary.get("top_opportunities", []) if exec_summary else []

        # Real provider health (exec_summary's "providers" section),
        # not a hardcoded "Healthy" regardless of actual status.
        providers = exec_summary.get("providers", {}) if exec_summary else {}
        platform_health = self._platform_health_label(providers)

        if "executive_hero" in selected:
            result["executive_hero"] = {
                **(portfolio_summary or {}),
                "ai_opportunities": len(opportunities),
                "platform_health": platform_health,
            }

        if "executive_kpis" in selected:
            result["executive_kpis"] = {
                "portfolio_value": (portfolio_summary or {}).get("portfolio_value", 0.0),
                "cash": (portfolio_summary or {}).get("cash", 0.0),
                "equity": (portfolio_summary or {}).get("total_equity", 0.0),
                "daily_pnl": (portfolio_summary or {}).get("daily_pnl", 0.0),
                "realized_pnl": (portfolio_summary or {}).get("realized_pnl", 0.0),
                "total_positions": (portfolio_summary or {}).get("total_positions", 0),
                "equity_portfolios": (
                    exec_summary.get("portfolio", {}).get("portfolios", 0)
                    if exec_summary and modules["stocks"]
                    else 0
                ),
                "forex_positions": (
                    forex_section.get("open_position_count", 0)
                    if isinstance(forex_section, dict)
                    else 0
                ),
                "option_positions": (
                    options_section.get("open_position_count", 0)
                    if isinstance(options_section, dict)
                    else 0
                ),
                "ai_opportunities": len(opportunities),
                "platform_health": platform_health,
            }

        if "asset_classes" in selected:
            result["asset_classes"] = {
                "equities": (
                    {
                        "portfolio_count": exec_summary.get("portfolio", {}).get("portfolios", 0) if exec_summary else 0,
                        "position_count": (portfolio_summary or {}).get("total_positions", 0),
                        "portfolio_value": (portfolio_summary or {}).get("portfolio_value", 0.0),
                        "cash": (portfolio_summary or {}).get("cash", 0.0),
                        "equity": (portfolio_summary or {}).get("total_equity", 0.0),
                        "daily_pnl": (portfolio_summary or {}).get("daily_pnl", 0.0),
                        "realized_pnl": (portfolio_summary or {}).get("realized_pnl", 0.0),
                    }
                    if modules["stocks"]
                    else self._not_licensed()
                ),
                "forex": (
                    {
                        "portfolio_count": forex_section.get("portfolio_count", 0) if isinstance(forex_section, dict) else 0,
                        "position_count": forex_section.get("open_position_count", 0) if isinstance(forex_section, dict) else 0,
                    }
                    if modules["forex"]
                    else self._not_licensed()
                ),
                "options": (
                    {"position_count": options_section.get("open_position_count", 0) if isinstance(options_section, dict) else 0}
                    if modules["options"]
                    else self._not_licensed()
                ),
                "crypto": (
                    {
                        "portfolio_count": crypto_section.get("portfolio_count", 0) if isinstance(crypto_section, dict) else 0,
                        "position_count": crypto_section.get("open_position_count", 0) if isinstance(crypto_section, dict) else 0,
                    }
                    if modules["crypto"]
                    else self._not_licensed()
                ),
            }

        if "executive_ai_brief" in selected:
            ai = exec_summary.get("ai", {}) if exec_summary else {}
            result["executive_ai_brief"] = {
                "confidence": ai.get("confidence", 0),
                "market_tone": ai.get("market_tone", "Neutral"),
                "executive_summary": ai.get("executive_summary", ""),
                "recommendations": ai.get("recommendations", []),
            }

        for section_name, exec_key in _EXEC_SUMMARY_SECTIONS.items():
            if section_name in selected:
                if exec_summary is not None and exec_key in exec_summary:
                    result[section_name] = exec_summary[exec_key]
                else:
                    result[section_name] = {
                        "available": False,
                        "reason": "This section failed to load.",
                    }

        return {

            "tenant_id": tenant_id,

            "generated_at": datetime.now(
                UTC,
            ).isoformat(),

            "requested_sections": selected,

            "returned_sections": sorted(
                result.keys(),
            ),

            "licensed_modules": {

                "stocks": modules["stocks"],

                "forex": modules["forex"],

                "options": modules["options"],

                "crypto": modules["crypto"],

            },

            # Every section lives here, and only here -- these used to
            # also be duplicated as top-level keys (executive_hero,
            # executive_kpis, asset_classes, executive_ai_brief),
            # meaning the exact same data appeared twice in the same
            # response under two different paths for no reason.
            "sections": result,

        }

    def _get_tenant_modules(self, tenant_id: str, *, is_super_admin: bool = False) -> dict[str, bool]:
        # A super admin bypasses tenant module licensing the same way
        # api.auth.module_entitlements.require_module already does for
        # every order-submission endpoint -- without this, a super
        # admin could successfully place a real order for a module
        # their tenant isn't licensed for (the write-side bypass),
        # then have this dashboard hide that exact position behind
        # "not licensed" (no read-side bypass), which is the
        # inconsistency behind a reported bug.
        if is_super_admin:
            return {"stocks": True, "options": True, "forex": True, "crypto": True}

        from api.auth.entitlements import get_module_flags_for_tenant
        from modules.db.models import Tenant

        try:
            self.db.rollback()
        except Exception:
            pass

        try:
            tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).one_or_none()
        except Exception:
            logger.exception("Failed to load tenant module entitlements | tenant_id=%s", tenant_id)
            try:
                self.db.rollback()
            except Exception:
                pass
            tenant = None

        if tenant is None:
            # No tenant row found -- fail toward the same defaults new
            # columns themselves default to, rather than block every
            # asset class over a lookup miss.
            return {"stocks": True, "options": True, "forex": True, "crypto": False}

        return get_module_flags_for_tenant(tenant)

    @staticmethod
    def _not_licensed() -> dict[str, Any]:
        return {"available": False, "reason": "module_not_licensed"}

    # ---------------------------------------------------------
    # Section builders
    # ---------------------------------------------------------

    def _get_exec_summary(
        self, *, tenant_id: str, is_super_admin: bool, roles: list[str] | None,
    ) -> dict[str, Any]:
        from api.services.executive_dashboard_api_service import (
            ExecutiveDashboardAPIService,
        )

        return ExecutiveDashboardAPIService(self.db).get_summary(
            tenant_id=tenant_id, is_super_admin=is_super_admin, roles=roles or [],
        )

    def _equities_section(
        self,
        exec_summary: dict[str, Any] | None,
        *,
        tenant_id: str | None = None,
        portfolio_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Tenant-wide stock portfolio/position counts, enriched with a
        specific portfolio's real equity/cash/performance/allocation/
        health when portfolio_id is available (the session's default
        portfolio, resolved at login -- see api/routers/auth.py's
        _resolve_default_portfolio_id). Without a portfolio_id (e.g.
        an older access token issued before that existed, or a tenant
        with no portfolios yet), this falls back to the tenant-wide
        counts alone -- additive, not a replacement, so a client that
        hasn't re-authenticated doesn't regress to nothing.

        No tenant-wide "recent orders" list exists yet for stocks
        (api.services.orders_api_service.OrdersAPIService is per-
        order/per-portfolio, not a list method), so this section
        doesn't include one rather than fake an empty list that looks
        like a real, checked field.
        """
        if exec_summary is None or "portfolio" not in exec_summary:
            return {"available": False, "reason": "This section failed to load."}

        result = dict(exec_summary["portfolio"])

        if portfolio_id and tenant_id:
            try:
                from api.services.portfolio_dashboard_api_service import PortfolioDashboardAPIService

                detail = PortfolioDashboardAPIService(self.db).get_dashboard(
                    tenant_id=tenant_id, portfolio_id=portfolio_id,
                )

                if detail is not None:
                    result["default_portfolio"] = detail

            except Exception:
                logger.exception(
                    "Failed to load default portfolio detail | portfolio_id=%s", portfolio_id,
                )
                try:
                    self.db.rollback()
                except Exception:
                    pass

        return result

    def _market_section(self) -> dict[str, Any]:
        """
        A compact bonds + commodities summary for the mobile home
        screen -- the same real data (FRED Treasury yields, Yahoo
        Finance commodity futures) backing the dedicated GET
        /api/v1/market/bond-market and /market/commodities endpoints,
        condensed for a mobile overview rather than duplicated with
        its own data source.
        """
        from api.services.market_api_service import MarketAPIService

        market_service = MarketAPIService()

        bond_data = market_service.get_bond_market()

        bonds_summary = None
        if bond_data.get("available", True) is not False:
            yield_curve = bond_data.get("yield_curve") or []
            ten_year = next((r.get("Yield") for r in yield_curve if r.get("Tenor") == "10Y"), None)
            two_year = next((r.get("Yield") for r in yield_curve if r.get("Tenor") == "2Y"), None)
            bonds_summary = {
                "yield_10y": ten_year,
                "yield_2y": two_year,
                "curve_10y_2y": (
                    round(ten_year - two_year, 3) if ten_year is not None and two_year is not None else None
                ),
                "regime": (bond_data.get("regime") or {}).get("regime"),
            }

        # A curated handful of the most commonly-watched commodities --
        # the full list has grown to 20 across 5 categories (precious
        # metals, energy, industrial metals, agriculture, livestock),
        # appropriate for the dedicated GET /api/v1/market/commodities
        # endpoint but too much for a compact mobile summary. Gold,
        # Silver, and Crude Oil (WTI) are both in "Precious Metals" and
        # "Energy", so fetching just those two categories (9 contracts)
        # covers every headline name without paying for agriculture/
        # livestock data that would be discarded immediately after.
        _MOBILE_HEADLINE_COMMODITIES = ("Gold", "Silver", "Crude Oil (WTI)", "Natural Gas")

        commodities_summary = None
        commodities_precious = market_service.get_commodities(category="Precious Metals")
        commodities_energy = market_service.get_commodities(category="Energy")

        combined_available = (
            commodities_precious.get("available", True) is not False
            or commodities_energy.get("available", True) is not False
        )

        if combined_available:
            all_fetched = (
                commodities_precious.get("commodities", [])
                + commodities_energy.get("commodities", [])
            )
            by_name = {c["name"]: c for c in all_fetched}

            commodities_summary = [
                {
                    "name": name,
                    "price": by_name[name].get("price"),
                    "change_1d_pct": by_name[name].get("change_1d_pct"),
                }
                for name in _MOBILE_HEADLINE_COMMODITIES
                if name in by_name and by_name[name].get("available")
            ]

        return {
            "bonds": bonds_summary if bonds_summary is not None else {"available": False},
            "commodities": (
                {"commodity_count": len(commodities_summary), "commodities": commodities_summary}
                if commodities_summary is not None
                else {"available": False}
            ),
        }

    def _forex_section(self, *, tenant_id: str, user_id: str | None) -> dict[str, Any]:
        """
        Forex portfolio count/combined balance across every portfolio
        this tenant/user has, plus open positions for the default
        portfolio specifically (a mobile dashboard's "what do I have
        open right now" view -- not every portfolio's positions, to
        keep this fast and avoid returning positions from portfolios
        the caller isn't currently looking at).
        """
        from api.services.forex_portfolios_api_service import (
            ForexPortfoliosAPIService,
        )
        from api.services.forex_orders_api_service import ForexOrdersAPIService

        # Order matters: get_positions() resolves (and auto-creates, if
        # none exists yet) the caller's default forex portfolio as a
        # side effect. Querying portfolio_statistics() first would miss
        # that just-created portfolio within this very call -- confirmed
        # directly, two consecutive calls to this method with identical
        # arguments returned portfolio_count 0 then 1.
        positions = ForexOrdersAPIService(self.db).get_positions(
            tenant_id=tenant_id, user_id=user_id,
        )
        stats = ForexPortfoliosAPIService(self.db).portfolio_statistics(
            tenant_id=tenant_id, user_id=user_id,
        )

        return {
            "portfolio_count": stats.get("portfolio_count", 0),
            "combined_balance": stats.get("combined_balance", 0.0),
            "default_portfolio": stats.get("default_portfolio"),
            "open_position_count": positions.get("position_count", 0),
            "open_positions": positions.get("positions", []),
        }

    def _options_section(self, *, tenant_id: str) -> dict[str, Any]:
        from api.services.options_orders_api_service import OptionsOrdersAPIService

        service = OptionsOrdersAPIService(self.db)

        positions = service.get_positions(tenant_id=tenant_id)
        recent_orders = service.get_order_history(tenant_id=tenant_id, limit=10)

        return {
            "open_position_count": positions.get("position_count", 0),
            "open_positions": positions.get("positions", []),
            "recent_order_count": recent_orders.get("order_count", 0),
            "recent_orders": recent_orders.get("orders", []),
        }

    def _crypto_section(self, *, tenant_id: str) -> dict[str, Any]:
        """
        Real crypto positions for this tenant -- reuses api.services.
        crypto_orders_api_service.CryptoOrdersAPIService.get_positions(),
        the same real, tenant-wide aggregation (across every portfolio
        the tenant has, including the dedicated "Crypto Trading"
        portfolio real crypto orders land in) already backing GET
        /api/v1/crypto/positions.

        This section used to be hardcoded to {"available": False,
        "reason": "Crypto trading is not yet available..."} -- written
        before real crypto trading existed on this platform, and never
        updated once it was built. Confirmed as a real, reported bug:
        a tenant with an actual crypto portfolio and real positions
        still saw "not yet available" here.
        """
        from api.services.crypto_orders_api_service import CryptoOrdersAPIService

        positions = CryptoOrdersAPIService(self.db).get_positions(tenant_id=tenant_id)

        portfolio_count = len({
            p["portfolio_id"] for p in positions.get("positions", []) if p.get("portfolio_id")
        })

        return {
            "portfolio_count": portfolio_count,
            "open_position_count": positions.get("position_count", 0),
            "open_positions": positions.get("positions", []),
        }

    def _portfolio_rollup(
        self,
        *,
        modules: dict[str, bool],
        exec_summary: dict[str, Any] | None,
        forex_section: dict[str, Any] | None,
        options_section: dict[str, Any] | None,
        crypto_section: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Cross-asset-class counts. Deliberately not a single combined
        dollar figure -- stock market value, forex account balance, and
        options notional aren't the same unit (different currencies,
        different meanings), and summing them would produce a number
        that looks precise but means nothing. This reports what each
        asset class actually has open, side by side, rather than a
        fabricated grand total. An unlicensed module shows the same
        not-licensed marker its own top-level section would, rather
        than a misleading zero count that looks like "you have none
        open" instead of "you can't see this at all".
        """
        equities = self._equities_section(exec_summary) if modules["stocks"] else None
        forex = forex_section if modules["forex"] else None
        options = options_section if modules["options"] else None
        crypto = crypto_section if modules["crypto"] else None

        return {
            "equities": (
                {
                    "portfolio_count": equities.get("portfolios", 0) if isinstance(equities, dict) else 0,
                    "position_count": equities.get("positions", 0) if isinstance(equities, dict) else 0,
                }
                if modules["stocks"]
                else self._not_licensed()
            ),
            "forex": (
                {
                    "portfolio_count": (forex or {}).get("portfolio_count", 0),
                    "position_count": (forex or {}).get("open_position_count", 0),
                }
                if modules["forex"]
                else self._not_licensed()
            ),
            "options": (
                {"position_count": (options or {}).get("open_position_count", 0)}
                if modules["options"]
                else self._not_licensed()
            ),
            "crypto": (
                {
                    "portfolio_count": (crypto or {}).get("portfolio_count", 0),
                    "position_count": (crypto or {}).get("open_position_count", 0),
                }
                if modules["crypto"]
                else self._not_licensed()
            ),
        }

    @staticmethod
    def _zero_portfolio_summary() -> dict[str, Any]:
        """
        Same shape as _mobile_portfolio_summary()'s real return, all
        zeroed -- used when modules["stocks"] is False, so the
        blended executive_hero/executive_kpis sections have something
        consistent to read defaults from without running the real
        (per-portfolio, multi-query) computation for a module the
        caller isn't licensed for.
        """
        return {
            "portfolio_value": 0.0,
            "cash": 0.0,
            "total_equity": 0.0,
            "daily_pnl": 0.0,
            "realized_pnl": 0.0,
            "buying_power": 0.0,
            "total_positions": 0,
        }

    @staticmethod
    def _platform_health_label(providers: dict[str, Any]) -> str:
        """
        Derives a human-readable status from the real provider
        success_rate (executive_dashboard_api_service's "providers"
        section) instead of a hardcoded value regardless of actual
        status. Thresholds are a simple, coarse read of the same
        number the "provider_health" section itself exposes in full --
        a mobile hero/KPI card wants one word, not the detail.
        """
        if not providers:
            return "Unknown"

        success_rate = providers.get("success_rate")
        if success_rate is None:
            return "Unknown"

        if success_rate >= 90:
            return "Healthy"
        if success_rate >= 50:
            return "Degraded"
        return "Unhealthy"

    def _mobile_portfolio_summary(
            self,
            *,
            tenant_id: str,
    ) -> dict[str, Any]:

        portfolio_service = PortfolioService(self.db)

        portfolios = portfolio_service.list_portfolios(
            tenant_id=tenant_id,
            active_only=True,
        )

        total_market_value = 0.0
        total_cash = 0.0
        total_equity = 0.0
        total_unrealized = 0.0
        total_realized = 0.0
        total_positions = 0

        for portfolio in portfolios:

            analytics = PortfolioAnalyticsService(
                self.db,
            ).get_analytics(
                tenant_id=tenant_id,
                portfolio_id=portfolio.id,
            )

            performance = PortfolioPerformanceService(
                self.db,
            ).get_performance(
                tenant_id=tenant_id,
                portfolio_id=portfolio.id,
            )

            if analytics:
                overview = analytics.get(
                    "overview",
                    {},
                )

                total_market_value += float(
                    overview.get(
                        "market_value",
                        0.0,
                    )
                )

                total_cash += float(
                    overview.get(
                        "cash_balance",
                        0.0,
                    )
                )

                total_equity += float(
                    overview.get(
                        "total_equity",
                        0.0,
                    )
                )

                total_positions += int(
                    overview.get(
                        "positions",
                        0,
                    )
                )

            if performance:
                total_unrealized += float(
                    performance.get(
                        "unrealized_pnl",
                        0.0,
                    )
                )

                total_realized += float(
                    performance.get(
                        "realized_pnl",
                        0.0,
                    )
                )

        return {

            "portfolio_value": round(
                total_market_value,
                2,
            ),

            "cash": round(
                total_cash,
                2,
            ),

            "total_equity": round(
                total_equity,
                2,
            ),

            "daily_pnl": round(
                total_unrealized,
                2,
            ),

            "realized_pnl": round(
                total_realized,
                2,
            ),

            "buying_power": round(
                total_cash,
                2,
            ),

            "total_positions": total_positions,
        }

    # ---------------------------------------------------------
    # Internal
    # ---------------------------------------------------------

    def _safe_call(self, section_name: str, call) -> dict[str, Any]:
        try:
            return call()
        except Exception:
            logger.exception("Mobile dashboard section failed | section=%s", section_name)
            try:
                self.db.rollback()
            except Exception:
                pass
            return {"available": False, "reason": "This section failed to load."}