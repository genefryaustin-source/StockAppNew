from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, UTC
from math import floor, isfinite
from typing import Any, Iterable

import pandas as pd
from sqlalchemy import text, bindparam

try:
    from modules.market_data.service import get_latest_price_map
except Exception:  # pragma: no cover - app fallback
    get_latest_price_map = None


@dataclass
class StockTradeRecommendation:
    symbol: str
    recommendation: str
    conviction_score: float
    confidence_score: float
    current_price: float | None
    entry_price: float | None
    stop_price: float | None
    target_price: float | None
    risk_reward: float | None
    suggested_qty: float
    max_position_value: float | None
    estimated_risk_dollars: float | None
    fundamental_score: float
    technical_score: float
    sentiment_score: float
    risk_score: float
    quality_score: float
    growth_score: float
    value_score: float
    momentum_score: float
    sector: str | None
    signal: str | None
    rationale: str
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["warnings"] = list(self.warnings or [])
        return data


class TradeRecommendationEngine:
    """
    Converts existing StockApp analytics snapshots into executable paper-trade ideas.

    This engine intentionally does not replace portfolio/order infrastructure. It reads
    analytics_snapshots and portfolio state, generates a trade setup, persists the idea
    to trade_recommendations, and lets OrderService execute through the existing
    trade_orders -> trade_fills -> portfolio_positions flow.
    """

    def __init__(self, db, tenant_id: str | None, portfolio_id: str | None = None):
        self.db = db
        self.tenant_id = tenant_id
        self.portfolio_id = portfolio_id

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
        self.db.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_trade_recommendations_tenant_created
            ON trade_recommendations (tenant_id, created_at DESC)
        """))
        self.db.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_trade_recommendations_portfolio_symbol
            ON trade_recommendations (portfolio_id, symbol)
        """))
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
    ) -> list[StockTradeRecommendation]:
        df = self._load_latest_analytics(
            watchlist_symbols=watchlist_symbols,
            candidate_limit=max(
                top_n * 10,
                100
            )
        )
        if df.empty:
            return []

        if not include_existing_positions and self.portfolio_id:
            held = self._load_current_position_symbols()
            if held:
                df = df[~df["symbol"].str.upper().isin(held)].copy()

        if df.empty:
            return []

        symbols = [str(x).upper() for x in df["symbol"].dropna().unique().tolist()]
        price_map = self._load_latest_prices(symbols)

        cash = float(cash_balance) if cash_balance is not None else self._load_cash_balance()
        recs: list[StockTradeRecommendation] = []

        for _, row in df.iterrows():
            rec = self._build_recommendation(
                row=row,
                price_map=price_map,
                cash_balance=cash,
                risk_budget_pct=float(risk_budget_pct),
                max_position_pct=float(max_position_pct),
            )
            if rec.conviction_score >= float(min_score):
                recs.append(rec)

        recs.sort(key=lambda r: (r.conviction_score, r.confidence_score), reverse=True)
        return recs[: int(top_n)]

    def save_recommendations(
        self,
        recommendations: list[StockTradeRecommendation],
        user_id: int | None = None,
    ) -> int:
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
                "symbol": payload["symbol"],
                "recommendation": payload["recommendation"],
                "conviction_score": payload["conviction_score"],
                "confidence_score": payload["confidence_score"],
                "current_price": payload["current_price"],
                "entry_price": payload["entry_price"],
                "stop_price": payload["stop_price"],
                "target_price": payload["target_price"],
                "risk_reward": payload["risk_reward"],
                "suggested_qty": payload["suggested_qty"],
                "max_position_value": payload["max_position_value"],
                "estimated_risk_dollars": payload["estimated_risk_dollars"],
                "fundamental_score": payload["fundamental_score"],
                "technical_score": payload["technical_score"],
                "sentiment_score": payload["sentiment_score"],
                "risk_score": payload["risk_score"],
                "quality_score": payload["quality_score"],
                "growth_score": payload["growth_score"],
                "value_score": payload["value_score"],
                "momentum_score": payload["momentum_score"],
                "sector": payload["sector"],
                "signal": payload["signal"],
                "rationale": payload["rationale"],
                "warnings": " | ".join(payload["warnings"]),
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
                WHERE portfolio_id = :portfolio_id
                  AND upper(symbol) = upper(:symbol)
                  AND COALESCE(executed, FALSE) = FALSE
                ORDER BY created_at DESC
                LIMIT 1
            )
        """), {
            "portfolio_id": self.portfolio_id,
            "symbol": symbol,
            "order_id": order_id,
        })
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
        """), {
            "portfolio_id": self.portfolio_id,
            "tenant_id": self.tenant_id,
            "limit": int(limit),
        }).mappings().all()
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------
    def _load_latest_analytics(self, watchlist_symbols: Iterable[str] | None = None) -> pd.DataFrame:
        params: dict[str, Any] = {"tenant_id": self.tenant_id}
        symbol_filter = ""
        sql_obj = text("""
            SELECT
                symbol, sector, composite_score, confidence_score,
                quality_score, growth_score, value_score, momentum_score,
                risk_score, sentiment_score, signal, signal_rationale,
                rating, rating_rationale, trend, rsi_14, sma_50, sma_200,
                support, resistance, vol_20d, max_drawdown_1y,
                gross_margin, operating_margin, fcf_margin, revenue_cagr,
                pe_ttm, ps_ttm, ev_ebitda, latest_volume, asof
            FROM analytics_snapshots
            WHERE (:tenant_id IS NULL OR tenant_id = :tenant_id)
        """)

        if watchlist_symbols:
            symbols = [str(s).upper().strip() for s in watchlist_symbols if str(s).strip()]
            if symbols:
                params["symbols"] = symbols
                sql_obj = text("""
                    SELECT
                        symbol, sector, composite_score, confidence_score,
                        quality_score, growth_score, value_score, momentum_score,
                        risk_score, sentiment_score, signal, signal_rationale,
                        rating, rating_rationale, trend, rsi_14, sma_50, sma_200,
                        support, resistance, vol_20d, max_drawdown_1y,
                        gross_margin, operating_margin, fcf_margin, revenue_cagr,
                        pe_ttm, ps_ttm, ev_ebitda, latest_volume, asof
                    FROM analytics_snapshots
                    WHERE (:tenant_id IS NULL OR tenant_id = :tenant_id)
                      AND upper(symbol) IN :symbols
                """).bindparams(bindparam("symbols", expanding=True))

        rows = self.db.execute(sql_obj, params).mappings().all()
        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df.columns = [str(c).lower() for c in df.columns]
        df["symbol"] = df["symbol"].astype(str).str.upper().str.strip()
        if "asof" in df.columns:
            df = (
                df.sort_values("asof")
                .drop_duplicates("symbol", keep="last")
            )

        # ---------------------------------
        # PRE-FILTER BEFORE PRICE LOOKUPS
        # ---------------------------------

        if "composite_score" in df.columns:
            df = df.sort_values(
                "composite_score",
                ascending=False
            )

        # Only evaluate top candidates
        df = df.head(250)

        return df

    def _load_current_position_symbols(self) -> set[str]:
        if not self.portfolio_id:
            return set()
        rows = self.db.execute(text("""
            SELECT symbol
            FROM portfolio_positions
            WHERE portfolio_id = :portfolio_id
              AND COALESCE(qty, 0) > 0
        """), {"portfolio_id": self.portfolio_id}).fetchall()
        return {str(r[0]).upper() for r in rows}

    def _load_cash_balance(self) -> float:
        if not self.portfolio_id:
            return 0.0
        try:
            from modules.portfolio.accounting_service import AccountingService
            return float(AccountingService(self.db).get_cash_balance(self.portfolio_id) or 0.0)
        except Exception:
            row = self.db.execute(text("""
                SELECT COALESCE(SUM(amount), 0) AS cash
                FROM portfolio_cash_ledger
                WHERE portfolio_id = :portfolio_id
            """), {"portfolio_id": self.portfolio_id}).fetchone()
            return float(row[0] or 0.0) if row else 0.0

    def _load_latest_prices(self, symbols: list[str]) -> dict[str, float]:

        if not hasattr(self, "_price_cache"):
            self._price_cache = {}

        out: dict[str, float] = {}

        if not symbols:
            return out

        # ---------------------------------
        # USE CACHE FIRST
        # ---------------------------------

        missing = []

        for sym in symbols:
            sym = str(sym).upper()

            if sym in self._price_cache:
                out[sym] = self._price_cache[sym]
            else:
                missing.append(sym)

        # ---------------------------------
        # FETCH ONLY MISSING SYMBOLS
        # ---------------------------------

        if missing and get_latest_price_map is not None:

            try:
                raw = get_latest_price_map(missing) or {}

                for k, v in raw.items():

                    val = self._safe_float(v)

                    if val and val > 0:
                        symbol = str(k).upper()

                        self._price_cache[symbol] = val
                        out[symbol] = val

            except Exception:
                pass

        return out

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------
    def _build_recommendation(
        self,
        row: pd.Series,
        price_map: dict[str, float],
        cash_balance: float,
        risk_budget_pct: float,
        max_position_pct: float,
    ) -> StockTradeRecommendation:
        symbol = str(row.get("symbol", "")).upper().strip()

        quality = self._score(row.get("quality_score"))
        growth = self._score(row.get("growth_score"))
        value = self._score(row.get("value_score"))
        momentum = self._score(row.get("momentum_score"))
        composite = self._score(row.get("composite_score"))
        sentiment = self._score(row.get("sentiment_score"), default=50.0)
        risk = self._score(row.get("risk_score"), default=50.0)
        confidence = self._score(row.get("confidence_score"), default=60.0)

        fundamental = (quality * 0.35) + (growth * 0.30) + (value * 0.20) + (sentiment * 0.15)
        technical = self._technical_score(row, momentum)

        conviction = (
            composite * 0.30 +
            fundamental * 0.25 +
            technical * 0.25 +
            sentiment * 0.10 +
            risk * 0.10
        )
        conviction = self._clamp(conviction, 0.0, 100.0)

        current_price = price_map.get(symbol) or self._safe_float(row.get("sma_50")) or self._safe_float(row.get("support"))
        entry = current_price if current_price and current_price > 0 else None
        stop, target, rr, warnings = self._build_trade_levels(row, entry)
        qty, max_value, risk_dollars = self._suggest_qty(
            cash_balance=cash_balance,
            entry=entry,
            stop=stop,
            risk_budget_pct=risk_budget_pct,
            max_position_pct=max_position_pct,
        )

        recommendation = self._action_label(conviction, confidence, rr, warnings)
        rationale = self._rationale(row, conviction, fundamental, technical, sentiment, risk, rr)

        return StockTradeRecommendation(
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
            sector=row.get("sector"),
            signal=row.get("signal"),
            rationale=rationale,
            warnings=warnings,
        )

    def _technical_score(self, row: pd.Series, momentum: float) -> float:
        score = momentum * 0.50
        price = self._safe_float(row.get("sma_50"))
        sma_200 = self._safe_float(row.get("sma_200"))
        rsi = self._safe_float(row.get("rsi_14"))
        trend = str(row.get("trend") or "").lower()
        signal = str(row.get("signal") or "").lower()

        if price and sma_200 and price > sma_200:
            score += 12
        if "up" in trend or "bull" in trend:
            score += 15
        if "buy" in signal or "strong" in signal:
            score += 10
        if rsi:
            if 45 <= rsi <= 70:
                score += 8
            elif rsi > 80:
                score -= 8
        return self._clamp(score, 0, 100)

    def _build_trade_levels(self, row: pd.Series, entry: float | None) -> tuple[float | None, float | None, float | None, list[str]]:
        warnings: list[str] = []
        if not entry or entry <= 0:
            return None, None, None, ["No valid current price available; review manually before trading."]

        support = self._safe_float(row.get("support"))
        resistance = self._safe_float(row.get("resistance"))
        vol_20d = self._safe_float(row.get("vol_20d"))

        stop_pct = 0.07
        if vol_20d:
            # vol_20d may be stored as 0.03 or 3.0. Normalize conservatively.
            vol_pct = vol_20d if vol_20d <= 1 else vol_20d / 100.0
            stop_pct = self._clamp(max(0.04, min(0.15, vol_pct * 2.0)), 0.04, 0.15)

        stop = support if support and support < entry else entry * (1.0 - stop_pct)
        target = resistance if resistance and resistance > entry else entry + ((entry - stop) * 2.0)

        risk = entry - stop
        reward = target - entry
        rr = reward / risk if risk > 0 else None

        if rr is None or rr < 1.5:
            warnings.append("Risk/reward is below 1.5; consider waiting for a better entry.")
        if stop >= entry:
            warnings.append("Stop price is not below entry; review support/resistance data.")
        if target <= entry:
            warnings.append("Target price is not above entry; review resistance data.")

        return stop, target, rr, warnings

    def _suggest_qty(
        self,
        cash_balance: float,
        entry: float | None,
        stop: float | None,
        risk_budget_pct: float,
        max_position_pct: float,
    ) -> tuple[float, float | None, float | None]:
        if not entry or entry <= 0 or cash_balance <= 0:
            return 0.0, None, None

        max_position_value = cash_balance * (max_position_pct / 100.0)
        qty_by_allocation = floor(max_position_value / entry)

        qty_by_risk = qty_by_allocation
        estimated_risk = None
        if stop and stop < entry:
            risk_per_share = entry - stop
            risk_budget_dollars = cash_balance * (risk_budget_pct / 100.0)
            qty_by_risk = floor(risk_budget_dollars / risk_per_share) if risk_per_share > 0 else qty_by_allocation

        qty = max(0, min(qty_by_allocation, qty_by_risk))
        if qty > 0 and stop and stop < entry:
            estimated_risk = qty * (entry - stop)
        return float(qty), float(max_position_value), estimated_risk

    def _action_label(self, conviction: float, confidence: float, rr: float | None, warnings: list[str]) -> str:
        if conviction >= 90 and confidence >= 70 and (rr or 0) >= 2.0 and not warnings:
            return "STRONG_BUY"
        if conviction >= 80 and confidence >= 60 and (rr or 0) >= 1.5:
            return "BUY"
        if conviction >= 70:
            return "WATCH"
        return "AVOID"

    def _rationale(self, row: pd.Series, conviction: float, fundamental: float, technical: float, sentiment: float, risk: float, rr: float | None) -> str:
        parts = [
            f"Conviction {conviction:.1f}/100",
            f"fundamental {fundamental:.1f}",
            f"technical {technical:.1f}",
            f"sentiment {sentiment:.1f}",
            f"risk quality {risk:.1f}",
        ]
        if rr:
            parts.append(f"risk/reward {rr:.2f}x")
        signal_rationale = row.get("signal_rationale") or row.get("rating_rationale")
        if signal_rationale:
            parts.append(str(signal_rationale)[:300])
        return "; ".join(parts) + "."

    # ------------------------------------------------------------------
    # Helpers
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
        # Existing code has used both -1..1, 0..1, and 0..100 scores.
        if -1.0 <= val <= 1.0:
            val = (val + 1.0) * 50.0 if val < 0 else val * 100.0
        elif 1.0 < val <= 10.0:
            val = val * 10.0
        return cls._clamp(val, 0.0, 100.0)

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, float(value)))

    @staticmethod
    def _round_or_none(value: float | None, ndigits: int = 2) -> float | None:
        if value is None:
            return None
        try:
            return round(float(value), ndigits)
        except Exception:
            return None
