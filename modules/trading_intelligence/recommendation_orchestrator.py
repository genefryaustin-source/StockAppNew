from __future__ import annotations

"""
modules/trading_intelligence/recommendation_orchestrator.py

Unified stock recommendation orchestration layer.

This module intentionally reuses the intelligence engines that already exist in
StockApp instead of creating another standalone scoring system:

- modules.analytics.rankings
- modules.analytics.ai_ranking_engine
- modules.analytics.adaptive_factor_engine
- modules.opportunity.opportunity_detection_engine
- modules.smart_money.smart_money_service / smart_money_signals
- modules.portfolio.ai_portfolio_orchestrator

The output is persisted into trade_recommendations, which then bridges into the
existing trade_orders -> trade_fills -> portfolio_positions paper-trading flow.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, UTC
from math import floor, isfinite
from types import SimpleNamespace
from typing import Any, Iterable, Optional

import pandas as pd
from sqlalchemy import bindparam, text

try:
    from modules.analytics.rankings import build_percentile_rankings, rank_symbols
except Exception:  # pragma: no cover
    build_percentile_rankings = None
    rank_symbols = None

try:
    from modules.analytics.ai_ranking_engine import enhance_rankings_with_ai
except Exception:  # pragma: no cover
    enhance_rankings_with_ai = None

try:
    from modules.analytics.adaptive_factor_engine import (
        compute_adaptive_weights,
        detect_market_regime,
    )
except Exception:  # pragma: no cover
    compute_adaptive_weights = None
    detect_market_regime = None

try:
    from modules.opportunity.opportunity_detection_engine import (
        detect_opportunity_signals,
        rank_asymmetric_opportunities,
    )
except Exception:  # pragma: no cover
    detect_opportunity_signals = None
    rank_asymmetric_opportunities = None

try:
    from modules.portfolio.ai_portfolio_orchestrator import (
        AIPortfolioCandidate,
        construct_ai_portfolio,
    )
except Exception:  # pragma: no cover
    AIPortfolioCandidate = None
    construct_ai_portfolio = None

try:
    from modules.market_data.service import get_latest_price_map
except Exception:  # pragma: no cover
    get_latest_price_map = None


@dataclass
class OrchestratedTradeRecommendation:
    symbol: str
    recommendation: str
    conviction_score: float
    confidence_score: float
    current_price: Optional[float]
    entry_price: Optional[float]
    stop_price: Optional[float]
    target_price: Optional[float]
    risk_reward: Optional[float]
    suggested_qty: float
    max_position_value: Optional[float]
    estimated_risk_dollars: Optional[float]
    fundamental_score: float
    technical_score: float
    sentiment_score: float
    risk_score: float
    quality_score: float
    growth_score: float
    value_score: float
    momentum_score: float
    sector: Optional[str]
    signal: Optional[str]
    rationale: str
    warnings: list[str]
    source_scores: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["warnings"] = list(self.warnings or [])
        return data


class RecommendationOrchestrator:
    """
    Unifies the existing StockApp analytics stack into executable trade ideas.
    """

    def __init__(self, db, tenant_id: str | None, portfolio_id: str | None = None):
        self.db = db
        self.tenant_id = tenant_id
        self.portfolio_id = str(portfolio_id) if portfolio_id is not None else None

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------
    def ensure_schema(self) -> None:
        self.db.execute(text("""
            CREATE TABLE IF NOT EXISTS trade_recommendations (
                id SERIAL PRIMARY KEY,
                tenant_id VARCHAR(100),
                portfolio_id VARCHAR(36),
                user_id INTEGER,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                symbol VARCHAR(20) NOT NULL,
                recommendation VARCHAR(30) NOT NULL,
                conviction_score DOUBLE PRECISION,
                confidence_score DOUBLE PRECISION,
                current_price DOUBLE PRECISION,
                entry_price DOUBLE PRECISION,
                stop_price DOUBLE PRECISION,
                target_price DOUBLE PRECISION,
                risk_reward DOUBLE PRECISION,
                suggested_qty DOUBLE PRECISION,
                max_position_value DOUBLE PRECISION,
                estimated_risk_dollars DOUBLE PRECISION,
                fundamental_score DOUBLE PRECISION,
                technical_score DOUBLE PRECISION,
                sentiment_score DOUBLE PRECISION,
                risk_score DOUBLE PRECISION,
                quality_score DOUBLE PRECISION,
                growth_score DOUBLE PRECISION,
                value_score DOUBLE PRECISION,
                momentum_score DOUBLE PRECISION,
                sector VARCHAR(120),
                signal VARCHAR(50),
                rationale TEXT,
                warnings TEXT,
                executed BOOLEAN DEFAULT FALSE,
                executed_order_id INTEGER,
                executed_at TIMESTAMP WITHOUT TIME ZONE,
                status VARCHAR(30) DEFAULT 'open'
            )
        """))

        migrations = [
            ("tenant_id", "ALTER TABLE trade_recommendations ADD COLUMN tenant_id VARCHAR(100)"),
            ("portfolio_id", "ALTER TABLE trade_recommendations ADD COLUMN portfolio_id VARCHAR(36)"),
            ("user_id", "ALTER TABLE trade_recommendations ADD COLUMN user_id INTEGER"),
            ("current_price", "ALTER TABLE trade_recommendations ADD COLUMN current_price DOUBLE PRECISION"),
            ("suggested_qty", "ALTER TABLE trade_recommendations ADD COLUMN suggested_qty DOUBLE PRECISION"),
            ("max_position_value", "ALTER TABLE trade_recommendations ADD COLUMN max_position_value DOUBLE PRECISION"),
            ("estimated_risk_dollars", "ALTER TABLE trade_recommendations ADD COLUMN estimated_risk_dollars DOUBLE PRECISION"),
            ("quality_score", "ALTER TABLE trade_recommendations ADD COLUMN quality_score DOUBLE PRECISION"),
            ("growth_score", "ALTER TABLE trade_recommendations ADD COLUMN growth_score DOUBLE PRECISION"),
            ("value_score", "ALTER TABLE trade_recommendations ADD COLUMN value_score DOUBLE PRECISION"),
            ("momentum_score", "ALTER TABLE trade_recommendations ADD COLUMN momentum_score DOUBLE PRECISION"),
            ("sector", "ALTER TABLE trade_recommendations ADD COLUMN sector VARCHAR(120)"),
            ("signal", "ALTER TABLE trade_recommendations ADD COLUMN signal VARCHAR(50)"),
            ("warnings", "ALTER TABLE trade_recommendations ADD COLUMN warnings TEXT"),
            ("executed_at", "ALTER TABLE trade_recommendations ADD COLUMN executed_at TIMESTAMP WITHOUT TIME ZONE"),
            ("status", "ALTER TABLE trade_recommendations ADD COLUMN status VARCHAR(30) DEFAULT 'open'"),
        ]
        for column_name, sql in migrations:
            if not self._column_exists("trade_recommendations", column_name):
                self.db.execute(text(sql))

        index_statements = [
            "CREATE INDEX IF NOT EXISTS ix_trade_recommendations_tenant_created ON trade_recommendations (tenant_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS ix_trade_recommendations_portfolio_symbol ON trade_recommendations (portfolio_id, symbol)",
            "CREATE INDEX IF NOT EXISTS ix_trade_recommendations_symbol ON trade_recommendations (symbol)",
            "CREATE INDEX IF NOT EXISTS ix_trade_recommendations_status ON trade_recommendations (status)",
            "CREATE INDEX IF NOT EXISTS ix_trade_recommendations_executed ON trade_recommendations (executed)",
        ]
        for stmt in index_statements:
            self.db.execute(text(stmt))
        self.db.commit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate_recommendations(
        self,
        top_n: int = 25,
        min_score: float = 70.0,
        include_existing_positions: bool = False,
        watchlist_symbols: Iterable[str] | None = None,
        cash_balance: float | None = None,
        risk_budget_pct: float = 1.0,
        max_position_pct: float = 10.0,
        sector_relative: bool = False,
        max_universe_symbols: int = 500,
    ) -> list[OrchestratedTradeRecommendation]:
        symbols = self._resolve_symbols(watchlist_symbols, max_universe_symbols=max_universe_symbols)
        if not symbols:
            return []

        if not include_existing_positions and self.portfolio_id:
            held = self._load_current_position_symbols()
            symbols = [s for s in symbols if s.upper() not in held]

        if not symbols:
            return []

        ranked_rows = self._build_ranked_rows(symbols, sector_relative=sector_relative)
        if not ranked_rows:
            return []

        adaptive_weights = self._build_adaptive_weights()
        ai_rows = self._enhance_with_ai(ranked_rows, adaptive_weights=adaptive_weights, limit=max(top_n * 4, top_n))
        if not ai_rows:
            return []

        symbols = [str(getattr(r, "symbol", "")).upper() for r in ai_rows if getattr(r, "symbol", "")]
        price_map = self._load_latest_prices(symbols)
        smart_money = self._load_smart_money_map(symbols)
        opportunities = self._build_opportunity_map(ai_rows)
        cash = float(cash_balance) if cash_balance is not None else self._load_cash_balance()
        portfolio_weights = self._build_portfolio_weights(ai_rows, opportunities, smart_money, max_position_pct=max_position_pct)

        recs: list[OrchestratedTradeRecommendation] = []
        for row in ai_rows:
            rec = self._compose_recommendation(
                row=row,
                price_map=price_map,
                smart_money=smart_money,
                opportunities=opportunities,
                portfolio_weights=portfolio_weights,
                cash_balance=cash,
                risk_budget_pct=float(risk_budget_pct),
                max_position_pct=float(max_position_pct),
            )
            if rec.conviction_score >= float(min_score):
                recs.append(rec)

        recs.sort(key=lambda x: (x.conviction_score, x.confidence_score, x.risk_reward or 0.0), reverse=True)
        return recs[: int(top_n)]

    def save_recommendations(self, recommendations: list[OrchestratedTradeRecommendation], user_id: int | None = None) -> int:
        self.ensure_schema()
        inserted = 0
        for rec in recommendations:
            payload = rec.to_dict()
            self.db.execute(text("""
                INSERT INTO trade_recommendations (
                    tenant_id, portfolio_id, user_id, created_at, symbol,
                    recommendation, conviction_score, confidence_score,
                    current_price, entry_price, stop_price, target_price,
                    risk_reward, suggested_qty, max_position_value,
                    estimated_risk_dollars, fundamental_score, technical_score,
                    sentiment_score, risk_score, quality_score, growth_score,
                    value_score, momentum_score, sector, signal, rationale,
                    warnings, executed, status
                ) VALUES (
                    :tenant_id, :portfolio_id, :user_id, :created_at, :symbol,
                    :recommendation, :conviction_score, :confidence_score,
                    :current_price, :entry_price, :stop_price, :target_price,
                    :risk_reward, :suggested_qty, :max_position_value,
                    :estimated_risk_dollars, :fundamental_score, :technical_score,
                    :sentiment_score, :risk_score, :quality_score, :growth_score,
                    :value_score, :momentum_score, :sector, :signal, :rationale,
                    :warnings, FALSE, 'open'
                )
            """), {
                "tenant_id": self.tenant_id,
                "portfolio_id": self.portfolio_id,
                "user_id": user_id,
                "created_at": datetime.now(UTC).replace(tzinfo=None),
                "symbol": payload.get("symbol"),
                "recommendation": payload.get("recommendation"),
                "conviction_score": payload.get("conviction_score"),
                "confidence_score": payload.get("confidence_score"),
                "current_price": payload.get("current_price"),
                "entry_price": payload.get("entry_price"),
                "stop_price": payload.get("stop_price"),
                "target_price": payload.get("target_price"),
                "risk_reward": payload.get("risk_reward"),
                "suggested_qty": payload.get("suggested_qty"),
                "max_position_value": payload.get("max_position_value"),
                "estimated_risk_dollars": payload.get("estimated_risk_dollars"),
                "fundamental_score": payload.get("fundamental_score"),
                "technical_score": payload.get("technical_score"),
                "sentiment_score": payload.get("sentiment_score"),
                "risk_score": payload.get("risk_score"),
                "quality_score": payload.get("quality_score"),
                "growth_score": payload.get("growth_score"),
                "value_score": payload.get("value_score"),
                "momentum_score": payload.get("momentum_score"),
                "sector": payload.get("sector"),
                "signal": payload.get("signal"),
                "rationale": payload.get("rationale"),
                "warnings": " | ".join(payload.get("warnings") or []),
            })
            inserted += 1
        self.db.commit()
        return inserted

    def mark_executed(self, symbol: str, order_id: int) -> None:
        self.ensure_schema()
        self.db.execute(text("""
            UPDATE trade_recommendations
            SET executed = TRUE,
                executed_order_id = :order_id,
                executed_at = CURRENT_TIMESTAMP,
                status = 'executed'
            WHERE id = (
                SELECT id
                FROM trade_recommendations
                WHERE (:portfolio_id IS NULL OR portfolio_id = :portfolio_id)
                  AND (:tenant_id IS NULL OR tenant_id = :tenant_id)
                  AND upper(symbol) = upper(:symbol)
                  AND COALESCE(executed, FALSE) = FALSE
                ORDER BY created_at DESC
                LIMIT 1
            )
        """), {"portfolio_id": self.portfolio_id, "tenant_id": self.tenant_id, "symbol": symbol, "order_id": order_id})
        self.db.commit()

    def load_recent_recommendations(self, limit: int = 50) -> pd.DataFrame:
        self.ensure_schema()
        rows = self.db.execute(text("""
            SELECT *
            FROM trade_recommendations
            WHERE (:portfolio_id IS NULL OR portfolio_id = :portfolio_id)
              AND (:tenant_id IS NULL OR tenant_id = :tenant_id)
            ORDER BY created_at DESC
            LIMIT :limit
        """), {"portfolio_id": self.portfolio_id, "tenant_id": self.tenant_id, "limit": int(limit)}).mappings().all()
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    # ------------------------------------------------------------------
    # Pipeline stages
    # ------------------------------------------------------------------
    def _resolve_symbols(self, symbols: Iterable[str] | None, max_universe_symbols: int = 500) -> list[str]:
        if symbols:
            out = [str(s).strip().upper() for s in symbols if str(s).strip()]
            return list(dict.fromkeys(out))

        rows = self.db.execute(text("""
            SELECT DISTINCT upper(symbol) AS symbol
            FROM analytics_snapshots
            WHERE (:tenant_id IS NULL OR tenant_id = :tenant_id)
              AND symbol IS NOT NULL
              AND length(symbol) <= 6
              AND symbol NOT LIKE '%^%'
            ORDER BY symbol
            LIMIT :limit
        """), {"tenant_id": self.tenant_id, "limit": int(max_universe_symbols or 500)}).mappings().all()
        return [r["symbol"] for r in rows if r.get("symbol")]

    def _build_ranked_rows(self, symbols: list[str], sector_relative: bool = False) -> list[Any]:
        if rank_symbols is not None:
            try:
                rows = rank_symbols(
                    self.db,
                    self.tenant_id,
                    symbols,
                    min_confidence=0.0,
                    require_composite=False,
                    use_percentiles=True,
                    sector_relative=sector_relative,
                )
                if rows:
                    return rows
            except Exception:
                self._safe_rollback()

        if build_percentile_rankings is not None:
            try:
                df = build_percentile_rankings(
                    self.db,
                    self.tenant_id,
                    symbols=symbols,
                    min_confidence=0.0,
                    sector_relative=sector_relative,
                )
                if df is not None and not df.empty:
                    return [self._df_row_to_rank_proxy(r) for _, r in df.iterrows()]
            except Exception:
                self._safe_rollback()

        df = self._load_latest_analytics(symbols)
        return [self._df_row_to_rank_proxy(r) for _, r in df.iterrows()]

    def _enhance_with_ai(self, ranked_rows: list[Any], adaptive_weights: Any = None, limit: int | None = None) -> list[Any]:
        if enhance_rankings_with_ai is not None:
            try:
                return enhance_rankings_with_ai(
                    ranked_rows,
                    limit=limit,
                    adaptive_weights=adaptive_weights,
                )
            except Exception:
                self._safe_rollback()
        return ranked_rows[:limit] if limit else ranked_rows

    def _build_adaptive_weights(self) -> Any:
        if compute_adaptive_weights is None:
            return None
        try:
            regime = detect_market_regime() if detect_market_regime is not None else None
            return compute_adaptive_weights(regime=regime)
        except Exception:
            return None

    def _build_opportunity_map(self, ai_rows: list[Any]) -> dict[str, Any]:
        if detect_opportunity_signals is None:
            return {}
        try:
            opportunities = detect_opportunity_signals(ai_rows, max_results=max(len(ai_rows), 25))
            if rank_asymmetric_opportunities is not None:
                opportunities = rank_asymmetric_opportunities(opportunities, max_results=max(len(ai_rows), 25))
            return {str(o.symbol).upper(): o for o in opportunities}
        except Exception:
            return {}

    def _build_portfolio_weights(self, ai_rows: list[Any], opportunities: dict[str, Any], smart_money: dict[str, dict], max_position_pct: float) -> dict[str, Any]:
        if AIPortfolioCandidate is None or construct_ai_portfolio is None:
            return {}
        candidates = []
        for row in ai_rows:
            symbol = str(getattr(row, "symbol", "")).upper()
            if not symbol:
                continue
            sm = smart_money.get(symbol, {})
            opp = opportunities.get(symbol)
            ai_score = self._score(getattr(row, "ai_score", getattr(row, "composite", 50.0)))
            ai_conf = self._score(getattr(row, "ai_confidence", getattr(row, "confidence", 50.0)))
            risk_score = self._score(getattr(row, "risk", 50.0), default=50.0)
            sm_score = self._score(sm.get("smart_money_score"), default=50.0) if sm else 50.0
            opp_conf = self._score(getattr(opp, "confidence", None), default=50.0) if opp else 50.0
            consensus = (ai_score * 0.55) + (sm_score * 0.25) + (opp_conf * 0.20)
            candidates.append(AIPortfolioCandidate(
                symbol=symbol,
                sector=str(getattr(row, "sector", "Unknown") or "Unknown"),
                ai_score=ai_score,
                consensus_score=round(consensus, 4),
                confidence=ai_conf,
                risk_score=risk_score,
                volatility=max(5.0, risk_score / 2.0),
                expected_alpha=max(0.0, (ai_score - 50.0) / 100.0),
                downside_risk=max(0.0, risk_score / 100.0),
                thesis=str(getattr(row, "ai_rationale", "") or getattr(row, "factor_summary", "")),
                bullish_factors=[str(getattr(row, "bull_thesis", ""))] if getattr(row, "bull_thesis", None) else [],
                bearish_factors=[str(getattr(row, "bear_thesis", ""))] if getattr(row, "bear_thesis", None) else [],
                risk_flags=[str(getattr(row, "risk_notes", ""))] if getattr(row, "risk_notes", None) else [],
            ))
        try:
            built = construct_ai_portfolio(
                candidates,
                max_positions=max(len(candidates), 1),
                max_position_weight=float(max_position_pct),
                sector_max_weight=30.0,
                cash_buffer=5.0,
            )
            return {c.symbol.upper(): c for c in built}
        except Exception:
            return {}

    def _compose_recommendation(
        self,
        row: Any,
        price_map: dict[str, float],
        smart_money: dict[str, dict],
        opportunities: dict[str, Any],
        portfolio_weights: dict[str, Any],
        cash_balance: float,
        risk_budget_pct: float,
        max_position_pct: float,
    ) -> OrchestratedTradeRecommendation:
        symbol = str(getattr(row, "symbol", "")).upper()
        quality = self._score(getattr(row, "quality", None))
        growth = self._score(getattr(row, "growth", None))
        value = self._score(getattr(row, "value", None))
        momentum = self._score(getattr(row, "momentum", None))
        risk = self._score(getattr(row, "risk", None), default=50.0)
        ai_score = self._score(getattr(row, "ai_score", getattr(row, "composite", None)))
        confidence = self._score(getattr(row, "ai_confidence", getattr(row, "confidence", None)), default=60.0)

        sm = smart_money.get(symbol, {})
        smart_score = self._score(sm.get("smart_money_score"), default=50.0) if sm else 50.0
        sm_conf = self._score(sm.get("confidence_score"), default=50.0) if sm else 50.0
        opp = opportunities.get(symbol)
        opp_score = self._score(getattr(opp, "signal_strength", None), default=50.0) if opp else 50.0
        opp_rr = self._safe_float(getattr(opp, "risk_reward_ratio", None)) if opp else None
        portfolio_candidate = portfolio_weights.get(symbol)
        portfolio_conviction = self._safe_float(getattr(portfolio_candidate, "composite_conviction", None), 50.0)

        fundamental = round((quality * 0.35) + (growth * 0.30) + (value * 0.20) + (smart_score * 0.15), 2)
        technical = round((momentum * 0.65) + (opp_score * 0.20) + ((100.0 - risk) * 0.15), 2)
        sentiment = round((sm_score_to_sentiment(sm) + opp_score) / 2.0, 2)

        conviction = (
            ai_score * 0.35
            + fundamental * 0.20
            + technical * 0.20
            + smart_score * 0.10
            + opp_score * 0.10
            + portfolio_conviction * 0.05
        )
        conviction = self._clamp(conviction, 0.0, 100.0)
        confidence = self._clamp((confidence * 0.70) + (sm_conf * 0.15) + (opp_score * 0.15), 0.0, 100.0)

        current_price = price_map.get(symbol) or self._load_price_from_db(symbol)
        entry = current_price if current_price and current_price > 0 else None
        stop, target, rr, warnings = self._build_trade_levels(entry, risk_score=risk, opportunity_rr=opp_rr)

        target_weight = self._safe_float(getattr(portfolio_candidate, "target_weight", None))
        if target_weight is None or target_weight <= 0:
            target_weight = float(max_position_pct)
        qty, max_value, risk_dollars = self._suggest_qty(
            cash_balance=cash_balance,
            entry=entry,
            stop=stop,
            risk_budget_pct=risk_budget_pct,
            target_weight_pct=target_weight,
            max_position_pct=max_position_pct,
        )

        signal = self._choose_signal(row, sm, opp)
        rationale, warning_text = self._build_rationale(row, sm, opp, portfolio_candidate, conviction, confidence, rr)
        warnings.extend(warning_text)
        recommendation = self._action_label(conviction, confidence, rr, warnings)

        return OrchestratedTradeRecommendation(
            symbol=symbol,
            recommendation=recommendation,
            conviction_score=round(conviction, 2),
            confidence_score=round(confidence, 2),
            current_price=self._round_or_none(current_price),
            entry_price=self._round_or_none(entry),
            stop_price=self._round_or_none(stop),
            target_price=self._round_or_none(target),
            risk_reward=self._round_or_none(rr),
            suggested_qty=float(qty),
            max_position_value=self._round_or_none(max_value),
            estimated_risk_dollars=self._round_or_none(risk_dollars),
            fundamental_score=round(fundamental, 2),
            technical_score=round(technical, 2),
            sentiment_score=round(sentiment, 2),
            risk_score=round(risk, 2),
            quality_score=round(quality, 2),
            growth_score=round(growth, 2),
            value_score=round(value, 2),
            momentum_score=round(momentum, 2),
            sector=str(getattr(row, "sector", "Unknown") or "Unknown"),
            signal=signal,
            rationale=rationale,
            warnings=warnings,
            source_scores={
                "ai_score": ai_score,
                "smart_money_score": smart_score,
                "opportunity_score": opp_score,
                "portfolio_conviction": portfolio_conviction,
            },
        )

    # ------------------------------------------------------------------
    # Data access
    # ------------------------------------------------------------------
    def _load_latest_analytics(self, symbols: list[str]) -> pd.DataFrame:
        if not symbols:
            return pd.DataFrame()
        sql = text("""
            SELECT *
            FROM analytics_snapshots
            WHERE (:tenant_id IS NULL OR tenant_id = :tenant_id)
              AND upper(symbol) IN :symbols
        """).bindparams(bindparam("symbols", expanding=True))
        rows = self.db.execute(sql, {"tenant_id": self.tenant_id, "symbols": [s.upper() for s in symbols]}).mappings().all()
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df.columns = [str(c).lower() for c in df.columns]
        df["symbol"] = df["symbol"].astype(str).str.upper()
        if "asof" in df.columns:
            df = df.sort_values("asof").drop_duplicates("symbol", keep="last")
        return df

    def _load_smart_money_map(self, symbols: list[str]) -> dict[str, dict]:
        if not symbols:
            return {}
        if not self._table_exists("smart_money_signals"):
            return {}
        try:
            sql = text("""
                SELECT DISTINCT ON (upper(symbol)) *
                FROM smart_money_signals
                WHERE upper(symbol) IN :symbols
                ORDER BY upper(symbol), created_at DESC NULLS LAST
            """).bindparams(bindparam("symbols", expanding=True))
            rows = self.db.execute(sql, {"symbols": [s.upper() for s in symbols]}).mappings().all()
            return {str(r["symbol"]).upper(): dict(r) for r in rows if r.get("symbol")}
        except Exception:
            self._safe_rollback()
            return {}

    def _load_latest_prices(self, symbols: list[str]) -> dict[str, float]:

        out: dict[str, float] = {}

        if not symbols:
            return out

        if get_latest_price_map is not None:
            try:

                print("=" * 80)
                print("RECOMMENDATION PRICE REQUEST")
                print("SYMBOLS REQUESTED:", len(symbols))
                print("FIRST 20:", symbols[:20])
                print("=" * 80)
                import traceback

                print("=" * 80)
                print("PRICE REQUEST CALLER")
                traceback.print_stack(limit=15)
                print("=" * 80)
                raw = get_latest_price_map(symbols) or {}

                print("RAW PRICES RETURNED:", len(raw))

                for i, (k, v) in enumerate(raw.items()):
                    print(
                        f"PRICE SAMPLE: {k} = {repr(v)} "
                        f"TYPE={type(v)}"
                    )

                    if i >= 20:
                        break

                valid_count = 0

                for k, v in raw.items():

                    val = self._safe_float(v)

                    if val and val > 0:
                        out[str(k).upper()] = val
                        valid_count += 1

                print("VALID PRICES RETURNED:", valid_count)

            except Exception as e:
                print(f"PRICE LOAD ERROR: {e}")

        for sym in symbols:
            if sym not in out:

                val = self._load_price_from_db(sym)

                if val and val > 0:
                    out[sym] = val

        print("FINAL PRICE COUNT:", len(out))

        return out

    def _load_price_from_db(self, symbol: str) -> Optional[float]:
        candidates = [
            ("analytics_snapshots", "latest_price"),
            ("analytics_snapshots", "close"),
            ("analytics_snapshots", "market_price"),
            ("analytics_snapshots", "sma_50"),
            ("price_history", "close"),
        ]
        for table_name, col in candidates:
            if not self._table_exists(table_name) or not self._column_exists(table_name, col):
                continue
            date_col = "asof" if self._column_exists(table_name, "asof") else "date" if self._column_exists(table_name, "date") else None
            order = f"ORDER BY {date_col} DESC NULLS LAST" if date_col else ""
            try:
                row = self.db.execute(text(f"""
                    SELECT {col} AS price
                    FROM {table_name}
                    WHERE upper(symbol) = upper(:symbol)
                      AND {col} IS NOT NULL
                    {order}
                    LIMIT 1
                """), {"symbol": symbol}).mappings().first()
                val = self._safe_float(row.get("price") if row else None)
                if val and val > 0:
                    return val
            except Exception:
                self._safe_rollback()
        return None

    def _load_current_position_symbols(self) -> set[str]:
        if not self.portfolio_id or not self._table_exists("portfolio_positions"):
            return set()
        try:
            rows = self.db.execute(text("""
                SELECT symbol
                FROM portfolio_positions
                WHERE portfolio_id = :portfolio_id
                  AND COALESCE(qty, 0) > 0
            """), {"portfolio_id": self.portfolio_id}).fetchall()
            return {str(r[0]).upper() for r in rows}
        except Exception:
            self._safe_rollback()
            return set()

    def _load_cash_balance(self) -> float:
        if not self.portfolio_id:
            return 0.0
        try:
            from modules.portfolio.accounting_service import AccountingService
            return float(AccountingService(self.db).get_cash_balance(self.portfolio_id) or 0.0)
        except Exception:
            self._safe_rollback()
        if self._table_exists("portfolio_cash_ledger"):
            try:
                row = self.db.execute(text("""
                    SELECT COALESCE(SUM(amount), 0) AS cash
                    FROM portfolio_cash_ledger
                    WHERE portfolio_id = :portfolio_id
                """), {"portfolio_id": self.portfolio_id}).fetchone()
                return float(row[0] or 0.0) if row else 0.0
            except Exception:
                self._safe_rollback()
        return 0.0

    # ------------------------------------------------------------------
    # Composition helpers
    # ------------------------------------------------------------------
    def _df_row_to_rank_proxy(self, row: pd.Series) -> Any:
        return SimpleNamespace(
            symbol=str(row.get("symbol", "")).upper(),
            sector=row.get("sector") or "Unknown",
            rating=row.get("rating"),
            composite=self._safe_float(row.get("percentile_composite"), self._safe_float(row.get("composite_score"), 50.0)),
            confidence=self._safe_float(row.get("confidence_score"), 50.0),
            quality=self._safe_float(row.get("quality_score"), self._safe_float(row.get("quality_pct"), 50.0)),
            growth=self._safe_float(row.get("growth_score"), self._safe_float(row.get("growth_pct"), 50.0)),
            value=self._safe_float(row.get("value_score"), self._safe_float(row.get("value_pct"), 50.0)),
            momentum=self._safe_float(row.get("momentum_score"), self._safe_float(row.get("momentum_pct"), 50.0)),
            risk=self._safe_float(row.get("risk_score"), self._safe_float(row.get("risk_pct"), 50.0)),
        )

    def _build_trade_levels(self, entry: Optional[float], risk_score: float, opportunity_rr: Optional[float] = None) -> tuple[Optional[float], Optional[float], Optional[float], list[str]]:
        warnings: list[str] = []
        if not entry or entry <= 0:
            return None, None, None, ["No valid current price available; review manually before trading."]
        stop_pct = self._clamp(0.04 + (risk_score / 100.0) * 0.08, 0.04, 0.15)
        stop = entry * (1.0 - stop_pct)
        rr_target = opportunity_rr if opportunity_rr and opportunity_rr >= 1.2 else 2.0
        rr_target = self._clamp(rr_target, 1.5, 4.0)
        target = entry + ((entry - stop) * rr_target)
        rr = (target - entry) / (entry - stop) if stop < entry else None
        if rr is None or rr < 1.5:
            warnings.append("Risk/reward is below 1.5; consider waiting for a better entry.")
        return stop, target, rr, warnings

    def _suggest_qty(self, cash_balance: float, entry: Optional[float], stop: Optional[float], risk_budget_pct: float, target_weight_pct: float, max_position_pct: float) -> tuple[float, Optional[float], Optional[float]]:
        if not entry or entry <= 0 or cash_balance <= 0:
            return 0.0, None, None
        target_pct = min(float(target_weight_pct or max_position_pct), float(max_position_pct))
        max_position_value = cash_balance * (target_pct / 100.0)
        qty_by_alloc = floor(max_position_value / entry)
        qty_by_risk = qty_by_alloc
        if stop and stop < entry:
            risk_per_share = entry - stop
            risk_budget = cash_balance * (float(risk_budget_pct) / 100.0)
            qty_by_risk = floor(risk_budget / risk_per_share) if risk_per_share > 0 else qty_by_alloc
        qty = max(0, min(qty_by_alloc, qty_by_risk))
        risk_dollars = qty * (entry - stop) if qty > 0 and stop and stop < entry else None
        return float(qty), float(max_position_value), risk_dollars

    def _action_label(
            self,
            conviction: float,
            confidence: float,
            rr: Optional[float],
            warnings: list[str],
    ) -> str:

        rr_val = rr or 0.0

        hard_warning = any(
            "No valid current price" in w
            for w in warnings
        )

        if hard_warning:
            return "WATCH"

        if conviction >= 85 and confidence >= 75 and rr_val >= 2.0:
            return "STRONG_BUY"

        if conviction >= 75 and confidence >= 65 and rr_val >= 1.5:
            return "BUY"

        if conviction >= 65:
            return "WATCH"

        return "AVOID"

    def _choose_signal(self, row: Any, sm: dict, opp: Any) -> Optional[str]:
        if opp and getattr(opp, "opportunity_type", None):
            return str(getattr(opp, "opportunity_type"))[:50]
        if sm and sm.get("signal"):
            return str(sm.get("signal"))[:50]
        rating = getattr(row, "rating", None)
        return str(rating)[:50] if rating else None

    def _build_rationale(self, row: Any, sm: dict, opp: Any, candidate: Any, conviction: float, confidence: float, rr: Optional[float]) -> tuple[str, list[str]]:
        parts = [
            f"Unified conviction {conviction:.1f}/100",
            f"confidence {confidence:.1f}/100",
        ]
        if rr:
            parts.append(f"risk/reward {rr:.2f}x")
        for attr in ("ai_rationale", "factor_summary", "bull_thesis"):
            val = getattr(row, attr, None)
            if val:
                parts.append(str(val))
        if sm and sm.get("rationale"):
            parts.append(f"Smart Money: {str(sm.get('rationale'))[:350]}")
        if opp and getattr(opp, "rationale", None):
            parts.append(f"Opportunity: {str(getattr(opp, 'rationale'))[:350]}")
        if candidate and getattr(candidate, "conviction_classification", None):
            parts.append(f"Portfolio sizing classification: {candidate.conviction_classification}; target weight {getattr(candidate, 'target_weight', 0):.2f}%")
        warnings = []
        if getattr(row, "risk_notes", None):
            warnings.append(str(getattr(row, "risk_notes")))
        if getattr(row, "bear_thesis", None):
            warnings.append(str(getattr(row, "bear_thesis")))
        if opp and getattr(opp, "warnings", None):
            warnings.extend([str(w) for w in getattr(opp, "warnings")])
        return "; ".join([p for p in parts if p])[:3000], warnings[:6]

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------
    def _table_exists(self, table_name: str) -> bool:
        try:
            return bool(self.db.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = ANY (current_schemas(false))
                      AND table_name = :table_name
                )
            """), {"table_name": table_name}).scalar())
        except Exception:
            self._safe_rollback()
            return False

    def _column_exists(self, table_name: str, column_name: str) -> bool:
        try:
            return bool(self.db.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = ANY (current_schemas(false))
                      AND table_name = :table_name
                      AND column_name = :column_name
                )
            """), {"table_name": table_name, "column_name": column_name}).scalar())
        except Exception:
            self._safe_rollback()
            return False

    def _safe_rollback(self) -> None:
        try:
            self.db.rollback()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Numeric helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _safe_float(value: Any, default: float | None = None) -> float | None:
        try:
            if value is None:
                return default
            out = float(value)
            if not isfinite(out):
                return default
            return out
        except Exception:
            return default

    @classmethod
    def _score(cls, value: Any, default: float = 50.0) -> float:
        val = cls._safe_float(value, default)
        if val is None:
            val = default
        if -1.0 <= val <= 1.0:
            val = (val + 1.0) * 50.0 if val < 0 else val * 100.0
        elif 1.0 < val <= 10.0:
            val = val * 10.0
        return cls._clamp(val, 0.0, 100.0)

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, float(value)))

    @staticmethod
    def _round_or_none(value: Any, ndigits: int = 2) -> Optional[float]:
        try:
            if value is None:
                return None
            return round(float(value), ndigits)
        except Exception:
            return None


def sm_score_to_sentiment(sm: dict) -> float:
    if not sm:
        return 50.0
    raw = sm.get("ai_score") or sm.get("accumulation_score") or sm.get("smart_money_score") or 50.0
    try:
        val = float(raw)
    except Exception:
        return 50.0
    if -1.0 <= val <= 1.0:
        return (val + 1.0) * 50.0 if val < 0 else val * 100.0
    if 1.0 < val <= 10.0:
        return val * 10.0
    return max(0.0, min(100.0, val))
