"""
Forex Quant Research Engine - Sprint 25 Phase 3

Production-ready, tenant-aware quantitative research integration for StockApp Forex.

Purpose
-------
This module converts live forex market inputs into institutional research outputs:
- Return, volatility, correlation, momentum, carry, mean-reversion, and breakout features
- Pair-level quant scores and rankings
- Basket-level regime/readiness diagnostics
- Optional Postgres persistence through SQLAlchemy sessions

Design goals
------------
- No hard dependency on Streamlit
- No mock-only output path
- Tenant-aware persistence: tenant_id, user_id, portfolio_id
- Safe operation when database is unavailable
- Compatible with the existing modules/forex architecture
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from math import isfinite, sqrt
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

try:
    import numpy as np
except Exception:  # pragma: no cover - numpy should exist in StockApp, but keep graceful fallback
    np = None  # type: ignore


DEFAULT_RESEARCH_TABLE = "forex_quant_research_snapshots"
DEFAULT_SIGNAL_TABLE = "forex_quant_research_signals"

MAJOR_PAIRS: Tuple[str, ...] = (
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD"
)
CROSS_PAIRS: Tuple[str, ...] = (
    "EURGBP", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "CHFJPY", "EURAUD", "GBPAUD"
)
DEFAULT_PAIRS: Tuple[str, ...] = MAJOR_PAIRS + CROSS_PAIRS


@dataclass
class ForexQuantSignal:
    tenant_id: str
    user_id: Optional[str]
    portfolio_id: Optional[str]
    symbol: str
    asof: datetime
    close: Optional[float]
    return_1d: Optional[float]
    return_5d: Optional[float]
    return_20d: Optional[float]
    volatility_20d: Optional[float]
    volatility_60d: Optional[float]
    momentum_score: float
    mean_reversion_score: float
    carry_score: float
    breakout_score: float
    trend_quality_score: float
    correlation_risk_score: float
    quant_score: float
    conviction: str
    signal: str
    rationale: str


@dataclass
class ForexQuantResearchSnapshot:
    tenant_id: str
    user_id: Optional[str]
    portfolio_id: Optional[str]
    asof: datetime
    universe_size: int
    analyzed_pairs: int
    bullish_count: int
    bearish_count: int
    neutral_count: int
    avg_quant_score: float
    avg_volatility_20d: Optional[float]
    strongest_pair: Optional[str]
    weakest_pair: Optional[str]
    highest_vol_pair: Optional[str]
    risk_regime: str
    research_summary: str


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        out = float(value)
        return out if isfinite(out) else None
    except Exception:
        return None


def _normalize_symbol(symbol: Any) -> str:
    return str(symbol or "").replace("/", "").replace("-", "").replace("_", "").upper().strip()


def _clip(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def _score_from_z(z: Optional[float], inverse: bool = False) -> float:
    if z is None or not isfinite(z):
        return 50.0
    z = max(-3.0, min(3.0, z))
    score = 50.0 + (z * 16.6667)
    if inverse:
        score = 100.0 - score
    return _clip(score)


def _series_zscore(series: pd.Series, value: Optional[float]) -> Optional[float]:
    value = _safe_float(value)
    if value is None:
        return None
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if len(clean) < 3:
        return None
    std = float(clean.std(ddof=0))
    if std <= 0:
        return None
    return (value - float(clean.mean())) / std


def _extract_price_frame(market_data: Any, pairs: Optional[Sequence[str]] = None) -> pd.DataFrame:
    """Normalize common live-data shapes into a wide close-price frame.

    Accepted forms:
    - DataFrame with columns: symbol, asof/date/timestamp, close/price
    - DataFrame already indexed by date with pair columns
    - Mapping[symbol] -> DataFrame/list with close data
    - Mapping[symbol] -> latest price float (limited analysis)
    """
    wanted = {_normalize_symbol(p) for p in (pairs or DEFAULT_PAIRS)}

    if market_data is None:
        return pd.DataFrame()

    if isinstance(market_data, pd.DataFrame):
        df = market_data.copy()
        cols = {str(c).lower(): c for c in df.columns}
        symbol_col = cols.get("symbol") or cols.get("pair") or cols.get("ticker")
        date_col = cols.get("asof") or cols.get("date") or cols.get("timestamp") or cols.get("datetime")
        close_col = cols.get("close") or cols.get("price") or cols.get("last") or cols.get("rate")
        if symbol_col and close_col:
            if date_col:
                df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            else:
                df["asof"] = utc_now()
                date_col = "asof"
            df[symbol_col] = df[symbol_col].map(_normalize_symbol)
            if wanted:
                df = df[df[symbol_col].isin(wanted)]
            pivot = df.pivot_table(index=date_col, columns=symbol_col, values=close_col, aggfunc="last")
            return pivot.sort_index().apply(pd.to_numeric, errors="coerce")
        return df.sort_index().apply(pd.to_numeric, errors="coerce")

    if isinstance(market_data, Mapping):
        frames: List[pd.Series] = []
        for raw_symbol, payload in market_data.items():
            symbol = _normalize_symbol(raw_symbol)
            if wanted and symbol not in wanted:
                continue
            if isinstance(payload, pd.DataFrame):
                cols = {str(c).lower(): c for c in payload.columns}
                close_col = cols.get("close") or cols.get("price") or cols.get("last") or cols.get("rate")
                date_col = cols.get("asof") or cols.get("date") or cols.get("timestamp") or cols.get("datetime")
                if not close_col:
                    continue
                series_df = payload.copy()
                if date_col:
                    idx = pd.to_datetime(series_df[date_col], errors="coerce")
                else:
                    idx = pd.RangeIndex(len(series_df))
                s = pd.Series(pd.to_numeric(series_df[close_col], errors="coerce").values, index=idx, name=symbol)
                frames.append(s)
            elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
                try:
                    frame = pd.DataFrame(payload)
                    if not frame.empty:
                        cols = {str(c).lower(): c for c in frame.columns}
                        close_col = cols.get("close") or cols.get("price") or cols.get("last") or cols.get("rate")
                        date_col = cols.get("asof") or cols.get("date") or cols.get("timestamp") or cols.get("datetime")
                        if close_col:
                            idx = pd.to_datetime(frame[date_col], errors="coerce") if date_col else pd.RangeIndex(len(frame))
                            frames.append(pd.Series(pd.to_numeric(frame[close_col], errors="coerce").values, index=idx, name=symbol))
                except Exception:
                    continue
            else:
                px = _safe_float(payload)
                if px is not None:
                    frames.append(pd.Series([px], index=[utc_now()], name=symbol))
        if frames:
            return pd.concat(frames, axis=1).sort_index()

    return pd.DataFrame()


def ensure_forex_quant_research_tables(db: Any) -> None:
    """Create Postgres-compatible research persistence tables if they do not exist."""
    if db is None:
        return

    ddl_snapshot = f"""
    CREATE TABLE IF NOT EXISTS {DEFAULT_RESEARCH_TABLE} (
        id BIGSERIAL PRIMARY KEY,
        tenant_id VARCHAR(100) NOT NULL,
        user_id VARCHAR(100),
        portfolio_id VARCHAR(100),
        asof TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        universe_size INTEGER NOT NULL DEFAULT 0,
        analyzed_pairs INTEGER NOT NULL DEFAULT 0,
        bullish_count INTEGER NOT NULL DEFAULT 0,
        bearish_count INTEGER NOT NULL DEFAULT 0,
        neutral_count INTEGER NOT NULL DEFAULT 0,
        avg_quant_score DOUBLE PRECISION,
        avg_volatility_20d DOUBLE PRECISION,
        strongest_pair VARCHAR(20),
        weakest_pair VARCHAR(20),
        highest_vol_pair VARCHAR(20),
        risk_regime VARCHAR(50),
        research_summary TEXT,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """
    ddl_signal = f"""
    CREATE TABLE IF NOT EXISTS {DEFAULT_SIGNAL_TABLE} (
        id BIGSERIAL PRIMARY KEY,
        tenant_id VARCHAR(100) NOT NULL,
        user_id VARCHAR(100),
        portfolio_id VARCHAR(100),
        symbol VARCHAR(20) NOT NULL,
        asof TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        close DOUBLE PRECISION,
        return_1d DOUBLE PRECISION,
        return_5d DOUBLE PRECISION,
        return_20d DOUBLE PRECISION,
        volatility_20d DOUBLE PRECISION,
        volatility_60d DOUBLE PRECISION,
        momentum_score DOUBLE PRECISION,
        mean_reversion_score DOUBLE PRECISION,
        carry_score DOUBLE PRECISION,
        breakout_score DOUBLE PRECISION,
        trend_quality_score DOUBLE PRECISION,
        correlation_risk_score DOUBLE PRECISION,
        quant_score DOUBLE PRECISION,
        conviction VARCHAR(30),
        signal VARCHAR(30),
        rationale TEXT,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """
    indexes = [
        f"CREATE INDEX IF NOT EXISTS idx_{DEFAULT_RESEARCH_TABLE}_tenant_asof ON {DEFAULT_RESEARCH_TABLE} (tenant_id, asof DESC);",
        f"CREATE INDEX IF NOT EXISTS idx_{DEFAULT_SIGNAL_TABLE}_tenant_asof ON {DEFAULT_SIGNAL_TABLE} (tenant_id, asof DESC);",
        f"CREATE INDEX IF NOT EXISTS idx_{DEFAULT_SIGNAL_TABLE}_tenant_symbol ON {DEFAULT_SIGNAL_TABLE} (tenant_id, symbol, asof DESC);",
    ]
    try:
        db.execute(text(ddl_snapshot))
        db.execute(text(ddl_signal))
        for stmt in indexes:
            db.execute(text(stmt))
        db.commit()
    except SQLAlchemyError:
        try:
            db.rollback()
        except Exception:
            pass
        raise


class ForexQuantResearchEngine:
    """Live quant research engine with optional Postgres persistence."""

    def __init__(self, db: Any = None, tenant_id: Optional[str] = None, user_id: Optional[str] = None, portfolio_id: Optional[str] = None):
        self.db = db
        self.tenant_id = str(tenant_id or "default")
        self.user_id = str(user_id) if user_id is not None else None
        self.portfolio_id = str(portfolio_id) if portfolio_id is not None else None

    def run_research(
        self,
        market_data: Any,
        pairs: Optional[Sequence[str]] = None,
        carry_inputs: Optional[Mapping[str, Any]] = None,
        persist: bool = True,
    ) -> Dict[str, Any]:
        price_frame = _extract_price_frame(market_data, pairs=pairs)
        universe = [_normalize_symbol(p) for p in (pairs or list(price_frame.columns) or DEFAULT_PAIRS)]
        universe = [p for p in universe if p]
        asof = utc_now()

        if price_frame.empty:
            snapshot = ForexQuantResearchSnapshot(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                portfolio_id=self.portfolio_id,
                asof=asof,
                universe_size=len(universe),
                analyzed_pairs=0,
                bullish_count=0,
                bearish_count=0,
                neutral_count=0,
                avg_quant_score=0.0,
                avg_volatility_20d=None,
                strongest_pair=None,
                weakest_pair=None,
                highest_vol_pair=None,
                risk_regime="NO_DATA",
                research_summary="No live forex price data was available for quantitative research.",
            )
            return {"snapshot": asdict(snapshot), "signals": [], "data_status": "NO_DATA"}

        price_frame = price_frame.dropna(axis=1, how="all")
        returns = price_frame.pct_change(fill_method=None)
        latest = price_frame.ffill().iloc[-1]

        signal_rows: List[ForexQuantSignal] = []
        ret20_values = returns.tail(20).mean() * 252 if len(returns) >= 20 else returns.mean() * 252
        vol20_values = returns.tail(20).std() * sqrt(252) if len(returns) >= 20 else returns.std() * sqrt(252)
        corr = returns.tail(60).corr() if len(returns) >= 3 else pd.DataFrame()

        for symbol in price_frame.columns:
            series = pd.to_numeric(price_frame[symbol], errors="coerce").dropna()
            if series.empty:
                continue
            r = pd.to_numeric(returns[symbol], errors="coerce").dropna()
            close = _safe_float(latest.get(symbol))
            ret_1d = _safe_float(series.pct_change(fill_method=None).iloc[-1]) if len(series) >= 2 else None
            ret_5d = _safe_float(series.iloc[-1] / series.iloc[-6] - 1.0) if len(series) >= 6 else None
            ret_20d = _safe_float(series.iloc[-1] / series.iloc[-21] - 1.0) if len(series) >= 21 else None
            vol20 = _safe_float(r.tail(20).std() * sqrt(252)) if len(r) >= 5 else None
            vol60 = _safe_float(r.tail(60).std() * sqrt(252)) if len(r) >= 20 else vol20

            momentum_score = _score_from_z(_series_zscore(ret20_values, ret20_values.get(symbol) if hasattr(ret20_values, "get") else None))

            if len(series) >= 20:
                ma20 = float(series.tail(20).mean())
                std20 = float(series.tail(20).std(ddof=0))
                z_px = ((float(series.iloc[-1]) - ma20) / std20) if std20 > 0 else 0.0
                mean_reversion_score = _score_from_z(z_px, inverse=True)
                high20 = float(series.tail(20).max())
                low20 = float(series.tail(20).min())
                breakout_score = 80.0 if float(series.iloc[-1]) >= high20 else 20.0 if float(series.iloc[-1]) <= low20 else 50.0
            else:
                mean_reversion_score = 50.0
                breakout_score = 50.0

            carry_raw = None
            if carry_inputs:
                carry_raw = _safe_float(carry_inputs.get(symbol) or carry_inputs.get(symbol[:3] + "/" + symbol[3:]))
            carry_score = _score_from_z(pd.Series(list(carry_inputs.values())) if carry_inputs else pd.Series(dtype=float), carry_raw) if carry_inputs else 50.0

            if len(series) >= 30:
                ma10 = float(series.tail(10).mean())
                ma30 = float(series.tail(30).mean())
                trend_quality_score = 65.0 if ma10 > ma30 else 35.0 if ma10 < ma30 else 50.0
            else:
                trend_quality_score = 50.0

            if not corr.empty and symbol in corr.columns:
                avg_abs_corr = float(corr[symbol].drop(labels=[symbol], errors="ignore").abs().mean())
                correlation_risk_score = _clip(100.0 - (avg_abs_corr * 100.0))
            else:
                correlation_risk_score = 50.0

            quant_score = _clip(
                momentum_score * 0.25
                + mean_reversion_score * 0.15
                + carry_score * 0.15
                + breakout_score * 0.15
                + trend_quality_score * 0.20
                + correlation_risk_score * 0.10
            )
            if quant_score >= 70:
                signal = "BULLISH"
                conviction = "HIGH" if quant_score >= 82 else "MEDIUM"
            elif quant_score <= 35:
                signal = "BEARISH"
                conviction = "HIGH" if quant_score <= 25 else "MEDIUM"
            else:
                signal = "NEUTRAL"
                conviction = "LOW"

            rationale = (
                f"{symbol} quant score {quant_score:.1f}: momentum {momentum_score:.1f}, "
                f"mean reversion {mean_reversion_score:.1f}, carry {carry_score:.1f}, "
                f"breakout {breakout_score:.1f}, trend quality {trend_quality_score:.1f}, "
                f"correlation risk {correlation_risk_score:.1f}."
            )
            signal_rows.append(ForexQuantSignal(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                portfolio_id=self.portfolio_id,
                symbol=symbol,
                asof=asof,
                close=close,
                return_1d=ret_1d,
                return_5d=ret_5d,
                return_20d=ret_20d,
                volatility_20d=vol20,
                volatility_60d=vol60,
                momentum_score=float(momentum_score),
                mean_reversion_score=float(mean_reversion_score),
                carry_score=float(carry_score),
                breakout_score=float(breakout_score),
                trend_quality_score=float(trend_quality_score),
                correlation_risk_score=float(correlation_risk_score),
                quant_score=float(quant_score),
                conviction=conviction,
                signal=signal,
                rationale=rationale,
            ))

        signals = sorted(signal_rows, key=lambda x: x.quant_score, reverse=True)
        bullish = sum(1 for s in signals if s.signal == "BULLISH")
        bearish = sum(1 for s in signals if s.signal == "BEARISH")
        neutral = sum(1 for s in signals if s.signal == "NEUTRAL")
        avg_score = float(sum(s.quant_score for s in signals) / len(signals)) if signals else 0.0
        vol_pairs = [s for s in signals if s.volatility_20d is not None]
        avg_vol = float(sum(s.volatility_20d for s in vol_pairs if s.volatility_20d is not None) / len(vol_pairs)) if vol_pairs else None
        risk_regime = "HIGH_VOL" if avg_vol is not None and avg_vol >= 0.18 else "NORMAL" if avg_vol is not None else "UNKNOWN"
        strongest = signals[0].symbol if signals else None
        weakest = signals[-1].symbol if signals else None
        highest_vol = max(vol_pairs, key=lambda s: s.volatility_20d or 0).symbol if vol_pairs else None
        summary = (
            f"Quant research analyzed {len(signals)} forex pairs. Average quant score is {avg_score:.1f}. "
            f"Strongest pair: {strongest or 'N/A'}; weakest pair: {weakest or 'N/A'}; risk regime: {risk_regime}."
        )
        snapshot = ForexQuantResearchSnapshot(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,
            asof=asof,
            universe_size=len(universe),
            analyzed_pairs=len(signals),
            bullish_count=bullish,
            bearish_count=bearish,
            neutral_count=neutral,
            avg_quant_score=avg_score,
            avg_volatility_20d=avg_vol,
            strongest_pair=strongest,
            weakest_pair=weakest,
            highest_vol_pair=highest_vol,
            risk_regime=risk_regime,
            research_summary=summary,
        )
        result = {
            "snapshot": asdict(snapshot),
            "signals": [asdict(s) for s in signals],
            "data_status": "LIVE_INPUT_ANALYZED",
        }
        if persist and self.db is not None:
            self.persist_result(result)
        return result

    def persist_result(self, result: Mapping[str, Any]) -> None:
        if self.db is None:
            return
        ensure_forex_quant_research_tables(self.db)
        snapshot = dict(result.get("snapshot") or {})
        signals = list(result.get("signals") or [])
        try:
            self.db.execute(text(f"""
                INSERT INTO {DEFAULT_RESEARCH_TABLE} (
                    tenant_id, user_id, portfolio_id, asof, universe_size, analyzed_pairs,
                    bullish_count, bearish_count, neutral_count, avg_quant_score,
                    avg_volatility_20d, strongest_pair, weakest_pair, highest_vol_pair,
                    risk_regime, research_summary
                ) VALUES (
                    :tenant_id, :user_id, :portfolio_id, :asof, :universe_size, :analyzed_pairs,
                    :bullish_count, :bearish_count, :neutral_count, :avg_quant_score,
                    :avg_volatility_20d, :strongest_pair, :weakest_pair, :highest_vol_pair,
                    :risk_regime, :research_summary
                )
            """), snapshot)
            for row in signals:
                self.db.execute(text(f"""
                    INSERT INTO {DEFAULT_SIGNAL_TABLE} (
                        tenant_id, user_id, portfolio_id, symbol, asof, close, return_1d,
                        return_5d, return_20d, volatility_20d, volatility_60d,
                        momentum_score, mean_reversion_score, carry_score, breakout_score,
                        trend_quality_score, correlation_risk_score, quant_score, conviction,
                        signal, rationale
                    ) VALUES (
                        :tenant_id, :user_id, :portfolio_id, :symbol, :asof, :close, :return_1d,
                        :return_5d, :return_20d, :volatility_20d, :volatility_60d,
                        :momentum_score, :mean_reversion_score, :carry_score, :breakout_score,
                        :trend_quality_score, :correlation_risk_score, :quant_score, :conviction,
                        :signal, :rationale
                    )
                """), row)
            self.db.commit()
        except SQLAlchemyError:
            try:
                self.db.rollback()
            except Exception:
                pass
            raise

    def load_latest(self, limit: int = 50) -> Dict[str, Any]:
        if self.db is None:
            return {"snapshot": None, "signals": [], "data_status": "NO_DB_SESSION"}
        ensure_forex_quant_research_tables(self.db)
        snapshot = None
        signals: List[Dict[str, Any]] = []
        snap_rows = self.db.execute(text(f"""
            SELECT * FROM {DEFAULT_RESEARCH_TABLE}
            WHERE tenant_id = :tenant_id
            ORDER BY asof DESC, id DESC
            LIMIT 1
        """), {"tenant_id": self.tenant_id}).mappings().all()
        if snap_rows:
            snapshot = dict(snap_rows[0])
            asof = snapshot.get("asof")
            sig_rows = self.db.execute(text(f"""
                SELECT * FROM {DEFAULT_SIGNAL_TABLE}
                WHERE tenant_id = :tenant_id AND asof = :asof
                ORDER BY quant_score DESC NULLS LAST, symbol ASC
                LIMIT :limit
            """), {"tenant_id": self.tenant_id, "asof": asof, "limit": int(limit)}).mappings().all()
            signals = [dict(r) for r in sig_rows]
        return {"snapshot": snapshot, "signals": signals, "data_status": "DB_LATEST" if snapshot else "DB_EMPTY"}


def run_forex_quant_research(
    market_data: Any,
    db: Any = None,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    pairs: Optional[Sequence[str]] = None,
    carry_inputs: Optional[Mapping[str, Any]] = None,
    persist: bool = True,
) -> Dict[str, Any]:
    return ForexQuantResearchEngine(db=db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id).run_research(
        market_data=market_data,
        pairs=pairs,
        carry_inputs=carry_inputs,
        persist=persist,
    )# =============================================================================
# Singleton Factory
# =============================================================================

_ENGINE = None


def get_forex_quant_research_engine(db=None):
    """
    Returns the singleton Forex Quant Research Engine.
    """

    global _ENGINE

    if (
        _ENGINE is None
        or (
            db is not None
            and getattr(_ENGINE, "db", None) is not db
        )
    ):
        _ENGINE = ForexQuantResearchEngine(db=db)

    return _ENGINE