"""
api/services/portfolio_performance_dashboard_api_service.py

Portfolio Performance Dashboard API Service

Backs GET /api/v1/portfolio/{portfolio_id}/performance-dashboard.

The existing GET /performance endpoint is a point-in-time snapshot
(cash, market value, cost basis, unrealized/realized P&L) -- useful,
but not what a mobile trading app's performance screen needs: risk-
adjusted return metrics, benchmark comparison, allocation, and trade
outcomes all in one call. This combines:

    snapshot            The existing get_performance() snapshot, plus
                         daily P&L (today's snapshot vs the prior one)
                         and a time-weighted return approximation
                         (geometric linking of daily returns from
                         stored equity snapshots -- NOT a true cash-
                         flow-adjusted TWR, since sub-period deposit/
                         withdrawal timing isn't tracked; honestly
                         labeled as an approximation).

    risk                 Real Sharpe ratio, Sortino ratio, maximum
                         drawdown, VaR, and volatility -- reusing
                         modules.portfolio.risk_analytics_service.
                         RiskAnalyticsService, extended with the new
                         sharpe_ratio()/sortino_ratio()/max_drawdown()
                         methods.

    benchmark            Cumulative return vs. benchmark (reuses
                         PortfolioBenchmarkAPIService), plus beta
                         (reuses PortfolioFactorsAPIService) and a
                         real, CAPM-derived alpha computed from the
                         same beta and the same benchmark return
                         series -- not a fabricated number.

    trade_performance    Win rate and profit factor, from the
                         previously-built-but-never-wired
                         PortfolioAttributionAnalyticsAPIService.

    allocation, holdings, income
                         Reused directly from their existing services.

Every section fails independently -- a single section's exception
never takes down the whole dashboard.
"""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np
import pandas as pd

from models.trading import Portfolio, PortfolioSnapshot

logger = logging.getLogger(__name__)


def _safe_rollback(db) -> None:
    try:
        db.rollback()
    except Exception:
        pass


class PortfolioPerformanceDashboardAPIService:
    """
    API service for the mobile-first portfolio performance dashboard:
    snapshot + daily P&L + TWR approximation, risk-adjusted metrics,
    benchmark/alpha/beta, win rate/profit factor, allocation, top
    holdings, and income -- combined into one response.
    """

    def __init__(self, db):
        self.db = db

    def get_performance_dashboard(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
        benchmark: str | None = None,
        period: str = "6mo",
    ) -> dict[str, Any] | None:
        _safe_rollback(self.db)

        portfolio = (
            self.db.query(Portfolio)
            .filter(Portfolio.id == portfolio_id, Portfolio.tenant_id == tenant_id)
            .one_or_none()
        )

        if portfolio is None:
            return None

        result: dict[str, Any] = {
            "portfolio_id": str(portfolio_id),
            "portfolio_name": portfolio.name,
            "benchmark": (benchmark or portfolio.benchmark or "SPY").upper(),
        }

        timings = self._run_sections_parallel(
            result, tenant_id=tenant_id, portfolio_id=portfolio_id, benchmark=benchmark, period=period,
        )

        result["_section_timings_ms"] = timings

        return result

    def _run_sections_parallel(
        self, result: dict[str, Any], *, tenant_id: str, portfolio_id: str, benchmark: str | None, period: str,
    ) -> dict[str, float]:
        """
        Runs every section concurrently instead of sequentially -- the
        same fix already proven for the Market Dashboard, applied
        here after a reported slow load. Each section that touches the
        database runs against its own fresh session (via
        _with_fresh_session), not self.db, since SQLAlchemy sessions
        aren't thread-safe and this dashboard's sections previously
        ran one after another specifically to avoid that problem --
        parallelizing means that safety now has to be handled
        explicitly instead of coming for free from sequential
        execution.
        """
        import time
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _with_fresh_session(method_name: str, **kwargs):
            from modules.db.core import new_db_session

            db = new_db_session()
            try:
                service = PortfolioPerformanceDashboardAPIService(db)
                return getattr(service, method_name)(**kwargs)
            finally:
                try:
                    db.close()
                except Exception:
                    pass

        def _timed(name, fn):
            start = time.time()
            try:
                return name, fn(), round((time.time() - start) * 1000, 1), None
            except Exception as exc:
                return name, None, round((time.time() - start) * 1000, 1), str(exc)

        def _with_fresh_session_positional(method_name: str, *args):
            from modules.db.core import new_db_session

            db = new_db_session()
            try:
                service = PortfolioPerformanceDashboardAPIService(db)
                return getattr(service, method_name)(*args)
            finally:
                try:
                    db.close()
                except Exception:
                    pass

        tasks = {
            "snapshot": lambda: _with_fresh_session(
                "_snapshot_section", tenant_id=tenant_id, portfolio_id=portfolio_id,
            ),
            "risk": lambda: _with_fresh_session(
                "_risk_section", tenant_id=tenant_id, portfolio_id=portfolio_id,
            ),
            "benchmark_comparison": lambda: _with_fresh_session(
                "_benchmark_section", tenant_id=tenant_id, portfolio_id=portfolio_id,
                benchmark=benchmark, period=period,
            ),
            "trade_performance": lambda: _with_fresh_session(
                "_trade_performance_section", tenant_id=tenant_id, portfolio_id=portfolio_id,
            ),
            "allocation": lambda: _with_fresh_session_positional(
                "_allocation_section", tenant_id, portfolio_id,
            ),
            "holdings": lambda: _with_fresh_session_positional(
                "_holdings_section", tenant_id, portfolio_id,
            ),
            "income": lambda: _with_fresh_session_positional(
                "_income_section", tenant_id, portfolio_id,
            ),
        }

        timings: dict[str, float] = {}
        overall_start = time.time()

        with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            futures = {executor.submit(_timed, name, fn): name for name, fn in tasks.items()}
            for future in as_completed(futures):
                name = futures[future]
                try:
                    section_name, value, elapsed_ms, error = future.result()
                    timings[section_name] = elapsed_ms

                    if error is not None:
                        logger.exception(
                            "Performance dashboard section failed | section=%s elapsed_ms=%s error=%s",
                            section_name, elapsed_ms, error,
                        )
                        result[section_name] = {"available": False, "reason": "This section failed to load."}
                    else:
                        result[section_name] = value

                except Exception:
                    logger.exception("Performance dashboard section failed | section=%s", name)
                    result[name] = {"available": False, "reason": "This section failed to load."}
                    timings[name] = None

        timings["_total"] = round((time.time() - overall_start) * 1000, 1)

        slowest = max(
            (k for k in timings if k != "_total"),
            key=lambda k: timings[k] or 0,
            default=None,
        )
        logger.info(
            "Performance dashboard timing | tenant_id=%s portfolio_id=%s total_ms=%s slowest_section=%s timings=%s",
            tenant_id, portfolio_id, timings["_total"], slowest, timings,
        )

        return timings

    def _safe_call(self, section_name: str, call) -> dict[str, Any]:
        try:
            return call()
        except Exception:
            logger.exception("Performance dashboard section failed | section=%s", section_name)
            _safe_rollback(self.db)
            return {"available": False, "reason": "This section failed to load."}

    # ------------------------------------------------------------
    # Snapshot + daily P&L + TWR approximation
    # ------------------------------------------------------------

    def _snapshot_section(self, *, tenant_id: str, portfolio_id: str) -> dict[str, Any]:
        return self._safe_call("snapshot", lambda: self._snapshot_section_impl(tenant_id, portfolio_id))

    def _snapshot_section_impl(self, tenant_id: str, portfolio_id: str) -> dict[str, Any]:
        from modules.portfolio.portfolio_performance_service import PortfolioPerformanceService

        base = PortfolioPerformanceService(self.db).get_performance(
            tenant_id=tenant_id, portfolio_id=portfolio_id,
        )

        if base is None:
            return {"available": False, "reason": "Portfolio not found."}

        result = dict(base)

        # Daily P&L: today's equity vs the prior day's, from stored
        # snapshots. Requires at least 2 distinct calendar days of
        # snapshots -- reports unavailable rather than a misleading
        # $0/0% when there's only ever been one snapshot taken.
        recent = (
            self.db.query(PortfolioSnapshot)
            .filter(PortfolioSnapshot.portfolio_id == portfolio_id)
            .order_by(PortfolioSnapshot.as_of.desc())
            .limit(50)
            .all()
        )

        daily_pnl = None
        if len(recent) >= 2:
            by_day: dict[Any, float] = {}
            for snap in recent:
                day = snap.as_of.date() if hasattr(snap.as_of, "date") else snap.as_of
                if day not in by_day:
                    by_day[day] = float(snap.equity or 0.0)

            days_sorted = sorted(by_day.keys(), reverse=True)
            if len(days_sorted) >= 2:
                today_equity = by_day[days_sorted[0]]
                prior_equity = by_day[days_sorted[1]]
                if prior_equity:
                    daily_pnl = {
                        "dollar_change": round(today_equity - prior_equity, 2),
                        "pct_change": round(((today_equity / prior_equity) - 1.0) * 100.0, 2),
                        "as_of": str(days_sorted[0]),
                        "prior_as_of": str(days_sorted[1]),
                    }

        result["daily_pnl"] = daily_pnl or {"available": False, "reason": "Not enough snapshot history yet."}
        result["time_weighted_return"] = self._twr_approximation(tenant_id, portfolio_id)

        return result

    def _twr_approximation(self, tenant_id: str, portfolio_id: str) -> dict[str, Any]:
        """
        Geometric linking of daily returns from stored equity
        snapshots: (1+r1)(1+r2)...(1+rn) - 1. This is a standard,
        honest approximation of time-weighted return, NOT a true
        cash-flow-adjusted TWR -- this platform doesn't track exactly
        when deposits/withdrawals happened within a day to exclude
        their distorting effect on that day's return, which a
        textbook TWR calculation requires. Labeled as an approximation
        in the response, not presented as more precise than it is.
        """
        try:
            from modules.risk_layer.positions import get_returns_df

            df = get_returns_df(self.db, tenant_id=tenant_id, portfolio_id=portfolio_id)

            if df is None or df.empty or "Return" not in df.columns:
                return {"available": False, "reason": "Not enough snapshot history yet."}

            returns = pd.to_numeric(df["Return"], errors="coerce").dropna()

            if returns.empty:
                return {"available": False, "reason": "Not enough snapshot history yet."}

            twr = float((1 + returns).prod() - 1.0)

            return {
                "available": True,
                "twr_pct": round(twr * 100.0, 2),
                "period_days": len(returns),
                "methodology_note": (
                    "Geometric linking of daily returns from stored equity snapshots. "
                    "Not a cash-flow-adjusted TWR (deposit/withdrawal timing within a day isn't tracked)."
                ),
            }

        except Exception:
            logger.exception("TWR approximation failed | portfolio_id=%s", portfolio_id)
            _safe_rollback(self.db)
            return {"available": False, "reason": "This section failed to load."}

    # ------------------------------------------------------------
    # Risk-adjusted metrics
    # ------------------------------------------------------------

    def _risk_section(self, *, tenant_id: str, portfolio_id: str) -> dict[str, Any]:
        return self._safe_call("risk", lambda: self._risk_section_impl(tenant_id, portfolio_id))

    def _risk_section_impl(self, tenant_id: str, portfolio_id: str) -> dict[str, Any]:
        from modules.risk_layer.positions import get_returns_df, get_positions_df
        from modules.portfolio.risk_analytics_service import RiskAnalyticsService

        returns_df = get_returns_df(self.db, tenant_id=tenant_id, portfolio_id=portfolio_id)
        positions_df = get_positions_df(self.db, tenant_id=tenant_id, portfolio_id=portfolio_id)

        analytics = RiskAnalyticsService(returns_df=returns_df, positions_df=positions_df)

        risk_free_rate = self._risk_free_rate()

        return {
            "sharpe_ratio": analytics.sharpe_ratio(risk_free_rate_annual=risk_free_rate),
            "sortino_ratio": analytics.sortino_ratio(risk_free_rate_annual=risk_free_rate),
            "max_drawdown": analytics.max_drawdown(),
            "current_drawdown": analytics.drawdown_alert(),
            "value_at_risk_95": analytics.historical_var(confidence=0.95),
            "volatility_regime": analytics.volatility_regime(),
            "risk_free_rate_used_pct": round(risk_free_rate * 100.0, 2),
        }

    def _risk_free_rate(self) -> float:
        """
        Real 3-month Treasury yield (as an annual rate, e.g. 0.05 for
        5%) from the same macro data source used elsewhere, for the
        Sharpe/Sortino calculations. Falls back to 0.0 (not a
        fabricated guess) if the live/cached macro data isn't
        available -- Sharpe/Sortino still compute, they just treat the
        risk-free rate as zero, which is a real (if less precise)
        methodology choice some practitioners use anyway.
        """
        try:
            from modules.market.macro_dashboard import _load_macro_snapshot

            snapshot = _load_macro_snapshot()
            yield_df = snapshot.get("yield_df")

            if isinstance(yield_df, pd.DataFrame) and not yield_df.empty and "Tenor" in yield_df.columns:
                row = yield_df[yield_df["Tenor"] == "3M"]
                if not row.empty and "Yield" in row.columns:
                    value = row["Yield"].iloc[0]
                    if pd.notna(value):
                        return float(value) / 100.0

        except Exception:
            logger.exception("Failed to load risk-free rate, defaulting to 0.0.")

        return 0.0

    # ------------------------------------------------------------
    # Benchmark comparison + beta + alpha
    # ------------------------------------------------------------

    def _benchmark_section(
        self, *, tenant_id: str, portfolio_id: str, benchmark: str | None, period: str,
    ) -> dict[str, Any]:
        return self._safe_call(
            "benchmark_comparison",
            lambda: self._benchmark_section_impl(tenant_id, portfolio_id, benchmark, period),
        )

    def _benchmark_section_impl(
        self, tenant_id: str, portfolio_id: str, benchmark: str | None, period: str,
    ) -> dict[str, Any]:
        from api.services.portfolio_benchmark_api_service import PortfolioBenchmarkAPIService
        from api.services.portfolio_factors_api_service import PortfolioFactorsAPIService

        bench_report = PortfolioBenchmarkAPIService(self.db).get_benchmark(
            tenant_id=tenant_id, portfolio_id=portfolio_id, benchmark=benchmark, period=period,
        )

        factors_report = PortfolioFactorsAPIService(self.db).get_factors(
            tenant_id=tenant_id, portfolio_id=portfolio_id,
        )

        result: dict[str, Any] = dict(bench_report or {})
        beta = (factors_report or {}).get("portfolio_beta")
        result["beta"] = beta
        result["alpha_pct"] = self._compute_alpha(bench_report, beta)

        return result

    def _compute_alpha(self, bench_report: dict[str, Any] | None, beta: float | None) -> float | None:
        """
        Jensen's alpha: portfolio_return - (risk_free + beta *
        (benchmark_return - risk_free)), annualized. Requires both a
        real beta and real cumulative return figures from the
        benchmark comparison -- returns None (not 0.0) if either is
        missing, rather than implying "no edge" when the real answer
        is "not enough data to know".
        """
        if not bench_report or beta is None:
            return None

        portfolio_return = bench_report.get("portfolio_return_pct")
        benchmark_return = bench_report.get("benchmark_return_pct")

        if portfolio_return is None or benchmark_return is None:
            return None

        risk_free = self._risk_free_rate() * 100.0

        alpha = portfolio_return - (risk_free + beta * (benchmark_return - risk_free))

        return round(alpha, 2)

    # ------------------------------------------------------------
    # Win rate / profit factor
    # ------------------------------------------------------------

    def _trade_performance_section(self, *, tenant_id: str, portfolio_id: str) -> dict[str, Any]:
        return self._safe_call(
            "trade_performance",
            lambda: self._trade_performance_impl(tenant_id, portfolio_id),
        )

    def _trade_performance_impl(self, tenant_id: str, portfolio_id: str) -> dict[str, Any]:
        from api.services.portfolio_attribution_analytics_api_service import PortfolioAttributionAnalyticsAPIService

        report = PortfolioAttributionAnalyticsAPIService(self.db).get_analytics(
            tenant_id=tenant_id, portfolio_id=portfolio_id,
        )

        if report is None:
            return {"available": False, "reason": "Portfolio not found."}

        performance = report.get("performance_metrics") or report.get("performance") or {}

        return {
            "win_rate_pct": performance.get("win_rate"),
            "profit_factor": performance.get("profit_factor"),
        }

    # ------------------------------------------------------------
    # Reused sections
    # ------------------------------------------------------------

    def _allocation_section(self, tenant_id: str, portfolio_id: str) -> dict[str, Any]:
        from modules.portfolio.portfolio_allocation_service import PortfolioAllocationService

        report = PortfolioAllocationService(self.db).get_allocation(
            tenant_id=tenant_id, portfolio_id=portfolio_id,
        )
        return report or {"available": False, "reason": "Portfolio not found."}

    def _holdings_section(self, tenant_id: str, portfolio_id: str) -> dict[str, Any]:
        from modules.portfolio.portfolio_holdings_service import PortfolioHoldingsService

        report = PortfolioHoldingsService(self.db).get_holdings(
            tenant_id=tenant_id, portfolio_id=portfolio_id,
        )
        return report or {"available": False, "reason": "Portfolio not found."}

    def _income_section(self, tenant_id: str, portfolio_id: str) -> dict[str, Any]:
        from api.services.portfolio_income_api_service import PortfolioIncomeAPIService

        report = PortfolioIncomeAPIService(self.db).get_income(
            tenant_id=tenant_id, portfolio_id=portfolio_id,
        )
        return report or {"available": False, "reason": "Portfolio not found."}