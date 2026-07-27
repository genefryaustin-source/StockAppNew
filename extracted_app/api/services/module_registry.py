"""
StockApp Module Registry

Central gateway into the existing StockApp business
modules.

The registry lazily imports and instantiates services on
first use, caches them, and returns the same instance
thereafter.

Routers should obtain services through this registry
rather than importing modules directly.

Architecture

Router
    ↓
Dependency
    ↓
ModuleRegistry
    ↓
modules/*
"""

from __future__ import annotations

import importlib
import logging
from typing import Any
from modules.db.core import new_db_session



logger = logging.getLogger(__name__)


class ModuleRegistry:
    """
    Lazy-loading registry for StockApp modules.
    """

    def __init__(self) -> None:

        self._instances: dict[str, Any] = {}

    # -----------------------------------------------------
    # Internal Loader
    # -----------------------------------------------------

    def _load(
        self,
        *,
        key: str,
        module_path: str,
        class_name: str,
        init_args: tuple = (),
        init_kwargs: dict | None = None,
    ) -> Any:

        if key in self._instances:
            instance = self._instances[key]

            # Refresh with a fresh session on every call, even for an
            # already-cached instance -- see this file's class
            # docstring update / commit message for why: reusing one
            # session forever across every request meant a single
            # unhandled failure, anywhere, at any point in the
            # process's lifetime, would permanently poison every
            # future request to this service until a full restart.
            old_db = getattr(instance, "db", None)
            if old_db is not None:
                try:
                    old_db.close()
                except Exception:
                    pass

            instance.db = new_db_session()

            return instance

        init_kwargs = init_kwargs or {}

        logger.info(
            "Loading module service: %s",
            key,
        )

        module = importlib.import_module(module_path)

        cls = getattr(module, class_name)

        #
        # Create a SQLAlchemy session
        #
        db = new_db_session()

        #
        # Instantiate the service
        #
        instance = cls(db)

        self._instances[key] = instance

        return instance

    # -----------------------------------------------------
    # Registry Management
    # -----------------------------------------------------

    def clear(self) -> None:

        self._instances.clear()

    def loaded_modules(self) -> list[str]:

        return sorted(self._instances.keys())

    def is_loaded(
        self,
        name: str,
    ) -> bool:

        return name in self._instances

    def portfolio(self):

        return self._load(

            key="portfolio",

            module_path="modules.portfolio.portfolio_service",

            class_name="PortfolioService",

        )

    def forex(self):

        return self._load(

            key="forex",

            module_path="modules.forex.forex_service",

            class_name="ForexService",

        )

    def options(self):

        return self._load(

            key="options",

            module_path="modules.options.options_service",

            class_name="OptionsService",

        )

    def crypto(self):

        return self._load(

            key="crypto",

            module_path="modules.crypto.crypto_service",

            class_name="CryptoService",

        )
    def market_data(self):
        # BROKEN, currently unused: modules.market_data.market_data_service
        # does not exist (the real module is modules.market_data.service,
        # a collection of functions, not a db-only-constructor class this
        # loader can instantiate). Nothing in this codebase currently
        # calls registry.market_data() -- quotes_api_service.py and
        # market_history_api_service.py import modules.market_data.service
        # functions directly instead. Left as-is rather than pointed at
        # an arbitrary class, since there's no single "the market data
        # service" this should resolve to.

        return self._load(

            key="market_data",

            module_path="modules.market_data.market_data_service",

            class_name="MarketDataService",

        )
    def fundamentals(self):

        return self._load(

            key="fundamentals",

            module_path="modules.fundamentals.fundamental_service",

            class_name="FundamentalService",

        )
    def sentiment(self):

        return self._load(

            key="sentiment",

            module_path="modules.sentiment.sentiment_service",

            class_name="SentimentService",

        )
    def indicators(self):

        return self._load(

            key="indicators",

            module_path="modules.indicators.indicator_service",

            class_name="IndicatorService",

        )
    def research(self):

        return self._load(

            key="research",

            module_path="modules.research.research_service",

            class_name="ResearchService",

        )
    def risk(self):

        return self._load(

            key="risk",

            module_path="modules.risk.risk_service",

            class_name="RiskService",

        )
    def reports(self):

        return self._load(

            key="reports",

            module_path="modules.reports.report_service",

            class_name="ReportService",

        )
    def forecasting(self):

        return self._load(

            key="forecasting",

            module_path="modules.forecasting.forecasting_service",

            class_name="ForecastingService",

        )
    def watchlists(self):

        return self._load(

            key="watchlists",

            module_path="api.services.watchlist_api_service",

            class_name="WatchlistAPIService",

        )
    def simulation(self):

        return self._load(

            key="simulation",

            module_path="modules.simulation.simulation_service",

            class_name="SimulationService",

        )
    def backtesting(self):

        return self._load(

            key="backtesting",

            module_path="modules.backtesting.backtesting_service",

            class_name="BacktestingService",

        )

    def positions(self):
        return self._load(

            key="positions",

            module_path="modules.portfolio.position_service",

            class_name="PositionService",

        )

    def orders(self):
        return self._load(

            key="orders",

            module_path="modules.portfolio.order_service",

            class_name="OrderService",

        )

    def accounting(self):
        return self._load(

            key="accounting",

            module_path="modules.portfolio.accounting_service",

            class_name="AccountingService",

        )

    def performance(self):
        return self._load(

            key="performance",

            module_path="modules.portfolio.portfolio_performance_service",

            class_name="PortfolioPerformanceService",

        )

    def performance_dashboard(self):
        return self._load(
            key="performance_dashboard",
            module_path="api.services.portfolio_performance_dashboard_api_service",
            class_name="PortfolioPerformanceDashboardAPIService",
        )

    def allocation(self):
        return self._load(

            key="allocation",

            module_path="modules.portfolio.portfolio_allocation_service",

            class_name="PortfolioAllocationService",

        )

    def history(self):
        return self._load(

            key="history",

            module_path="modules.portfolio.portfolio_history_service",

            class_name="PortfolioHistoryService",

        )

    def holdings(self):
        return self._load(

            key="holdings",

            module_path="modules.portfolio.portfolio_holdings_service",

            class_name="PortfolioHoldingsService",

        )

    def analytics(self):
        return self._load(

            key="analytics",

            module_path="modules.portfolio.portfolio_analytics_service",

            class_name="PortfolioAnalyticsService",

        )

    def portfolio_risk(self):
        return self._load(

            key="portfolio_risk",

            module_path="modules.portfolio.portfolio_risk_api_service",

            class_name="PortfolioRiskAPIService",

        )

    def portfolio_recommendations(self):
        return self._load(
            key="portfolio_recommendations",
            module_path="api.services.portfolio_recommendation_api_service",
            class_name="PortfolioRecommendationAPIService",
        )

    def portfolio_attribution(self):
        return self._load(

            key="portfolio_attribution",

            module_path="api.services.portfolio_attribution_api_service",

            class_name="PortfolioAttributionAPIService",

        )

    def portfolio_attribution_analytics(
            self,
    ):
        return self._load(

            key="portfolio_attribution_analytics",

            module_path=(
                "api.services."
                "portfolio_attribution_analytics_api_service"
            ),

            class_name=(
                "PortfolioAttributionAnalyticsAPIService"
            ),

        )

    def portfolio_optimization(self):
        return self._load(
            key="portfolio_optimization",
            module_path="api.services.portfolio_optimization_api_service",
            class_name="PortfolioOptimizationAPIService",
        )

    def portfolio_benchmark(self):
        return self._load(
            key="portfolio_benchmark",
            module_path="api.services.portfolio_benchmark_api_service",
            class_name="PortfolioBenchmarkAPIService",
        )

    def portfolio_scenarios(self):
        return self._load(
            key="portfolio_scenarios",
            module_path="api.services.portfolio_scenarios_api_service",
            class_name="PortfolioScenariosAPIService",
        )

    def portfolio_factors(self):
        return self._load(
            key="portfolio_factors",
            module_path="api.services.portfolio_factors_api_service",
            class_name="PortfolioFactorsAPIService",
        )

    def portfolio_correlation(self):
        return self._load(
            key="portfolio_correlation",
            module_path="api.services.portfolio_correlation_api_service",
            class_name="PortfolioCorrelationAPIService",
        )

    def portfolio_rebalance(self):
        return self._load(
            key="portfolio_rebalance",
            module_path="api.services.portfolio_rebalance_api_service",
            class_name="PortfolioRebalanceAPIService",
        )

    def portfolio_cash(self):
        return self._load(
            key="portfolio_cash",
            module_path="api.services.portfolio_cash_api_service",
            class_name="PortfolioCashAPIService",
        )

    def portfolio_income(self):
        return self._load(
            key="portfolio_income",
            module_path="api.services.portfolio_income_api_service",
            class_name="PortfolioIncomeAPIService",
        )

    def portfolio_health(self):
        return self._load(
            key="portfolio_health",
            module_path="api.services.portfolio_health_api_service",
            class_name="PortfolioHealthAPIService",
        )

    def portfolio_dashboard(self):
        return self._load(
            key="portfolio_dashboard",
            module_path="api.services.portfolio_dashboard_api_service",
            class_name="PortfolioDashboardAPIService",
        )

    def portfolio_recommendations_lifecycle(self):
        return self._load(
            key="portfolio_recommendations_lifecycle",
            module_path="api.services.portfolio_recommendations_lifecycle_api_service",
            class_name="PortfolioRecommendationsLifecycleAPIService",
        )

    def portfolio_recommendations_performance(self):
        return self._load(
            key="portfolio_recommendations_performance",
            module_path="api.services.portfolio_recommendations_performance_api_service",
            class_name="PortfolioRecommendationsPerformanceAPIService",
        )

    def portfolio_recommendations_targets(self):
        return self._load(
            key="portfolio_recommendations_targets",
            module_path="api.services.portfolio_recommendations_targets_api_service",
            class_name="PortfolioRecommendationsTargetsAPIService",
        )

    def portfolio_recommendations_stops(self):
        return self._load(
            key="portfolio_recommendations_stops",
            module_path="api.services.portfolio_recommendations_stops_api_service",
            class_name="PortfolioRecommendationsStopsAPIService",
        )

    def portfolio_recommendations_alerts(self):
        return self._load(
            key="portfolio_recommendations_alerts",
            module_path="api.services.portfolio_recommendations_alerts_api_service",
            class_name="PortfolioRecommendationsAlertsAPIService",
        )

    def portfolio_recommendations_command_center(self):
        return self._load(
            key="portfolio_recommendations_command_center",
            module_path="api.services.portfolio_recommendations_command_center_api_service",
            class_name="PortfolioRecommendationsCommandCenterAPIService",
        )

    def orders_api(self):
        return self._load(
            key="orders_api",
            module_path="api.services.orders_api_service",
            class_name="OrdersAPIService",
        )

    def quotes(self):
        return self._load(
            key="quotes",
            module_path="api.services.quotes_api_service",
            class_name="QuotesAPIService",
        )

    def market_history(self):
        return self._load(
            key="market_history",
            module_path="api.services.market_history_api_service",
            class_name="MarketHistoryAPIService",
        )

    def screener(self):
        return self._load(
            key="screener",
            module_path="api.services.screener_api_service",
            class_name="ScreenerAPIService",
        )

    def recommendations_feed(self):
        return self._load(
            key="recommendations_feed",
            module_path="api.services.recommendations_feed_api_service",
            class_name="RecommendationsFeedAPIService",
        )

    def analytics_feed(self):
        return self._load(
            key="analytics_feed",
            module_path="api.services.analytics_feed_api_service",
            class_name="AnalyticsFeedAPIService",
        )

    def risk_feed(self):
        return self._load(
            key="risk_feed",
            module_path="api.services.risk_feed_api_service",
            class_name="RiskFeedAPIService",
        )

    def alerts(self):
        return self._load(
            key="alerts",
            module_path="api.services.alerts_api_service",
            class_name="AlertsAPIService",
        )

    def portfolio_reports(self):
        return self._load(
            key="portfolio_reports",
            module_path="api.services.portfolio_reports_api_service",
            class_name="PortfolioReportsAPIService",
        )

    def ipo(self):
        return self._load(
            key="ipo",
            module_path="api.services.ipo_api_service",
            class_name="IPOAPIService",
        )

    def preipo(self):
        return self._load(
            key="preipo",
            module_path="api.services.preipo_api_service",
            class_name="PreIPOAPIService",
        )

    def options_orders(self):
        return self._load(
            key="options_orders",
            module_path="api.services.options_orders_api_service",
            class_name="OptionsOrdersAPIService",
        )

    def options_market_data(self):
        return self._load(
            key="options_market_data",
            module_path="api.services.options_market_data_api_service",
            class_name="OptionsMarketDataAPIService",
        )

    def forex_orders(self):
        return self._load(
            key="forex_orders",
            module_path="api.services.forex_orders_api_service",
            class_name="ForexOrdersAPIService",
        )

    def forex_market_data(self):
        return self._load(
            key="forex_market_data",
            module_path="api.services.forex_market_data_api_service",
            class_name="ForexMarketDataAPIService",
        )

    def forex_portfolios(self):
        return self._load(
            key="forex_portfolios",
            module_path="api.services.forex_portfolios_api_service",
            class_name="ForexPortfoliosAPIService",
        )

    def forex_position_management(self):
        return self._load(
            key="forex_position_management",
            module_path="api.services.forex_position_management_api_service",
            class_name="ForexPositionManagementAPIService",
        )

    def executive_dashboard(self):
        return self._load(
            key="executive_dashboard",
            module_path="api.services.executive_dashboard_api_service",
            class_name="ExecutiveDashboardAPIService",
        )

    def executive_mobile_dashboard(self):
        return self._load(
            key="executive_mobile_dashboard",
            module_path="api.services.executive_mobile_dashboard_api_service",
            class_name="ExecutiveMobileDashboardAPIService",
        )

    def ai_dashboard(self):
        return self._load(
            key="ai_dashboard",
            module_path="api.services.ai_dashboard_api_service",
            class_name="AIDashboardAPIService",
        )

    def crypto_orders(self):
        return self._load(
            key="crypto_orders",
            module_path="api.services.crypto_orders_api_service",
            class_name="CryptoOrdersAPIService",
        )

    def crypto_market_data(self):
        return self._load(
            key="crypto_market_data",
            module_path="api.services.crypto_market_data_api_service",
            class_name="CryptoMarketDataAPIService",
        )

    def market(self):
        return self._load(
            key="market",
            module_path="api.services.market_api_service",
            class_name="MarketAPIService",
        )





module_registry = ModuleRegistry()
def get_module_registry():
    return module_registry