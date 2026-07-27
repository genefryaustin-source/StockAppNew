"""
api/services/ai_dashboard_api_service.py

AI Dashboard API Service

Backs GET /api/v1/ai/dashboard, /portfolio, /risk, /execution,
/opportunities, /market-regime, /daily-briefing.

No new "AI" logic lives here -- every section wraps a real, existing
module, with one fix applied upstream in this same session:

    market_regime   modules.analytics.market_regime_inputs (new) +
                     modules.analytics.adaptive_factor_engine.
                     detect_market_regime() (pre-existing, genuinely
                     real threshold-based classification -- the
                     problem was its one confirmed-live caller fed it
                     hardcoded literal constants; fixed at the source
                     in modules/analytics/ranking_ui.py, and this
                     service uses the same real computation).

    opportunities   modules.dashboard.executive_dashboard.
                     get_top_opportunities() -- already real, already
                     tested (backs GET /api/v1/executive/summary).

    risk            modules.dashboard.executive_dashboard.
                     get_risk_metrics() -- same, already real/tested.

    portfolio       modules.analytics.rankings.rank_symbols() (real,
                     analytics_snapshots-backed) converted into
                     modules.portfolio.ai_portfolio_orchestrator.
                     AIPortfolioCandidate objects, then
                     construct_ai_portfolio() -- the same real
                     ranking pipeline "AI Rankings" uses, feeding the
                     same real portfolio construction "AI Portfolio"
                     uses, without replicating either page's own
                     Streamlit-specific UI flow (or, notably, without
                     replicating AI Portfolio's own hardcoded-regime-
                     input call -- this service's market_regime
                     section is what's real).

    execution       Real trade_orders/trade_fills activity (stocks) --
                     not modules.analytics.autonomous_execution_*,
                     which are elaborate but completely unreachable
                     from the live app (confirmed: no caller anywhere
                     in app.py) and therefore unproven.

    daily_briefing, dashboard
                    Aggregate the sections above; no separate data
                     source of their own.
"""

from __future__ import annotations

import logging
from datetime import datetime, UTC, timedelta
from typing import Any

logger = logging.getLogger(__name__)


class AIDashboardAPIService:
    """API service for the AI dashboard endpoints."""

    def __init__(self, db):
        self.db = db

    # ---------------------------------------------------------
    # Market regime
    # ---------------------------------------------------------

    def get_market_regime(self) -> dict[str, Any]:
        """
        Real market-regime classification: honest threshold-based
        rules (modules.analytics.adaptive_factor_engine.
        detect_market_regime) over real, computed statistics
        (modules.analytics.market_regime_inputs) from stored SPY
        price history. Reports {"available": false, "reason": ...}
        rather than a regime if there isn't enough stored price
        history yet -- never falls back to a fabricated reading.
        """
        try:
            from modules.analytics.market_regime_inputs import compute_market_regime_inputs
            from modules.analytics.adaptive_factor_engine import detect_market_regime

            inputs = compute_market_regime_inputs(self.db)

            if inputs is None:
                return {
                    "available": False,
                    "reason": (
                        "Not enough stored price history for the market "
                        "benchmark yet to compute this honestly."
                    ),
                }

            regime = detect_market_regime(
                market_return_30d=inputs["market_return_30d"],
                market_return_90d=inputs["market_return_90d"],
                volatility_30d=inputs["volatility_30d"],
                drawdown_90d=inputs["drawdown_90d"],
            )

            return {
                "regime": regime.regime,
                "confidence": regime.confidence,
                "volatility_level": regime.volatility_level,
                "momentum_state": regime.momentum_state,
                "risk_state": regime.risk_state,
                "detected_at": regime.detected_at.isoformat(),
                "inputs": {
                    "benchmark_symbol": inputs["benchmark_symbol"],
                    "market_return_30d": inputs["market_return_30d"],
                    "market_return_90d": inputs["market_return_90d"],
                    "volatility_30d": inputs["volatility_30d"],
                    "drawdown_90d": inputs["drawdown_90d"],
                    "trading_days_available": inputs["trading_days_available"],
                },
            }

        except Exception:
            logger.exception("Failed to compute market regime.")
            self._safe_rollback()
            return {"available": False, "reason": "This section failed to load."}

    # ---------------------------------------------------------
    # Opportunities / Risk (reuse the executive dashboard's own,
    # already-tested sections directly)
    # ---------------------------------------------------------

    def get_opportunities(
        self, *, tenant_id: str, is_super_admin: bool, roles: list[str], limit: int = 10,
    ) -> dict[str, Any]:
        try:
            import modules.dashboard.executive_dashboard as ed

            user = {"role": "super_admin" if is_super_admin else (roles[0] if roles else "client"), "tenant_id": tenant_id}
            df = ed.get_top_opportunities(self.db, user, limit)

            records = df.to_dict(orient="records") if hasattr(df, "to_dict") else []

            return {"opportunity_count": len(records), "opportunities": records}

        except Exception:
            logger.exception("Failed to load AI opportunities.")
            self._safe_rollback()
            return {"available": False, "reason": "This section failed to load."}

    def get_risk(self, *, tenant_id: str, is_super_admin: bool, roles: list[str]) -> dict[str, Any]:
        try:
            import modules.dashboard.executive_dashboard as ed

            user = {"role": "super_admin" if is_super_admin else (roles[0] if roles else "client"), "tenant_id": tenant_id}
            return ed.get_risk_metrics(self.db, user)

        except Exception:
            logger.exception("Failed to load AI risk metrics.")
            self._safe_rollback()
            return {"available": False, "reason": "This section failed to load."}

    # ---------------------------------------------------------
    # Portfolio
    # ---------------------------------------------------------

    def get_portfolio(
        self, *, tenant_id: str, max_positions: int = 20,
    ) -> dict[str, Any]:
        """
        Real, ranked-and-weighted AI portfolio: fetches this tenant's
        universe from stored analytics snapshots, ranks it (the same
        real pipeline "AI Rankings" uses), and constructs a weighted
        portfolio from those rankings (the same real construction
        logic "AI Portfolio" uses) -- without replicating either
        page's own Streamlit UI flow, and without AI Portfolio's own
        separate, hardcoded-regime-input call (this service's
        market_regime section is the real one).
        """
        try:
            from modules.analytics.snapshot_cache import get_latest_snapshots_df
            from modules.analytics.rankings import rank_symbols
            from modules.portfolio.ai_portfolio_orchestrator import (
                AIPortfolioCandidate,
                construct_ai_portfolio,
            )

            snapshot_df = get_latest_snapshots_df(self.db, tenant_id)

            if snapshot_df is None or snapshot_df.empty:
                return {
                    "available": False,
                    "reason": (
                        "No analytics snapshots available yet for this tenant. "
                        "Populate a universe and run analytics first."
                    ),
                }

            symbols = (
                snapshot_df["symbol"].dropna().astype(str).str.upper().unique().tolist()
            )

            ranked_rows = rank_symbols(self.db, tenant_id=tenant_id, symbols=symbols)

            if not ranked_rows:
                return {
                    "available": False,
                    "reason": "No AI rankings available for this tenant's universe yet.",
                }

            def _safe_score(value, default: float = 50.0) -> float:
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    return default
                return default if value != value else value  # value != value is True only for NaN

            candidates = [
                AIPortfolioCandidate(
                    symbol=row.symbol,
                    sector=row.sector or "Unknown",
                    ai_score=_safe_score(row.composite),
                    consensus_score=_safe_score(row.composite),
                    confidence=_safe_score(row.confidence),
                    risk_score=_safe_score(row.risk),
                )
                for row in ranked_rows
            ]

            portfolio = construct_ai_portfolio(candidates, max_positions=max_positions)

            positions = [
                {
                    "symbol": c.symbol,
                    "sector": c.sector,
                    "target_weight": c.target_weight,
                    "ai_score": c.ai_score,
                    "confidence": c.confidence,
                    "risk_score": c.risk_score,
                    "conviction_label": c.conviction_label,
                }
                for c in portfolio
            ]

            return {
                "position_count": len(positions),
                "positions": positions,
                "universe_size": len(symbols),
                "ranked_count": len(ranked_rows),
            }

        except Exception:
            logger.exception("Failed to construct AI portfolio.")
            self._safe_rollback()
            return {"available": False, "reason": "This section failed to load."}

    # ---------------------------------------------------------
    # Execution
    # ---------------------------------------------------------

    def get_execution(self, *, tenant_id: str, lookback_days: int = 7) -> dict[str, Any]:
        """
        Real execution activity from actual order/fill records
        (stocks) -- not modules.analytics.autonomous_execution_*,
        which are elaborate but completely unreachable from the live
        app (no caller anywhere in app.py) and therefore unproven.
        """
        try:
            from models.trading import TradeOrder, TradeFill, Portfolio

            since = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=lookback_days)

            portfolio_ids = [
                row[0] for row in
                self.db.query(Portfolio.id).filter(Portfolio.tenant_id == tenant_id).all()
            ]

            if not portfolio_ids:
                return {
                    "order_count": 0,
                    "fill_count": 0,
                    "fill_rate": 0.0,
                    "status_breakdown": {},
                    "lookback_days": lookback_days,
                }

            orders = (
                self.db.query(TradeOrder)
                .filter(TradeOrder.portfolio_id.in_(portfolio_ids))
                .filter(TradeOrder.created_at >= since)
                .all()
            )

            status_breakdown: dict[str, int] = {}
            for o in orders:
                status = str(getattr(o, "status", "unknown") or "unknown")
                status_breakdown[status] = status_breakdown.get(status, 0) + 1

            fill_count = (
                self.db.query(TradeFill)
                .filter(TradeFill.order_id.in_([o.id for o in orders]))
                .count()
                if orders else 0
            )

            order_count = len(orders)
            fill_rate = round(fill_count / order_count, 4) if order_count else 0.0

            return {
                "order_count": order_count,
                "fill_count": fill_count,
                "fill_rate": fill_rate,
                "status_breakdown": status_breakdown,
                "lookback_days": lookback_days,
            }

        except Exception:
            logger.exception("Failed to load AI execution summary.")
            self._safe_rollback()
            return {"available": False, "reason": "This section failed to load."}

    # ---------------------------------------------------------
    # Daily briefing / Dashboard (aggregates)
    # ---------------------------------------------------------

    def get_daily_briefing(
        self, *, tenant_id: str, is_super_admin: bool, roles: list[str],
    ) -> dict[str, Any]:
        """
        A plain-language summary assembled from the real sections
        above -- template-based, not generative-AI-written text. No
        LLM call is made here; this composes real numbers into
        sentences, honestly.
        """
        regime = self.get_market_regime()
        risk = self.get_risk(tenant_id=tenant_id, is_super_admin=is_super_admin, roles=roles)
        opportunities = self.get_opportunities(
            tenant_id=tenant_id, is_super_admin=is_super_admin, roles=roles, limit=3,
        )

        headline_parts = []

        if regime.get("available", True) is not False:
            headline_parts.append(
                f"Market regime: {regime.get('regime', 'unknown')} "
                f"(confidence {regime.get('confidence', 0):.0f}%, "
                f"risk state {regime.get('risk_state', 'unknown')})."
            )
        else:
            headline_parts.append("Market regime: not enough price history to assess yet.")

        opp_count = opportunities.get("opportunity_count", 0) if opportunities.get("available", True) is not False else 0
        if opp_count:
            top_symbols = [o.get("Symbol") or o.get("symbol") for o in opportunities.get("opportunities", [])[:3]]
            top_symbols = [s for s in top_symbols if s]
            headline_parts.append(
                f"{opp_count} flagged opportunit{'y' if opp_count == 1 else 'ies'}"
                + (f", led by {', '.join(top_symbols)}." if top_symbols else ".")
            )
        else:
            headline_parts.append("No flagged opportunities right now.")

        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "summary": " ".join(headline_parts),
            "market_regime": regime,
            "risk": risk,
            "top_opportunities": opportunities,
        }

    def get_dashboard(
        self, *, tenant_id: str, user_id: str | None, is_super_admin: bool, roles: list[str],
    ) -> dict[str, Any]:
        """Every AI section in one response, each failing independently."""

        return {
            "tenant_id": tenant_id,
            "generated_at": datetime.now(UTC).isoformat(),
            "market_regime": self.get_market_regime(),
            "risk": self.get_risk(tenant_id=tenant_id, is_super_admin=is_super_admin, roles=roles),
            "opportunities": self.get_opportunities(
                tenant_id=tenant_id, is_super_admin=is_super_admin, roles=roles,
            ),
            "portfolio": self.get_portfolio(tenant_id=tenant_id),
            "execution": self.get_execution(tenant_id=tenant_id),
        }

    # ---------------------------------------------------------
    # Internal
    # ---------------------------------------------------------

    def _safe_rollback(self) -> None:
        try:
            self.db.rollback()
        except Exception:
            pass