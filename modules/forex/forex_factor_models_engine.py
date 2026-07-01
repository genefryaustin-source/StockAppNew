"""
Forex Factor Models Engine - Sprint 25 Phase 4

Production-ready, tenant-aware live factor model integration for StockApp Forex.

Purpose
-------
This module converts live forex prices and optional institutional inputs into
pair-level factor exposures, composite factor rankings, and factor portfolio
signals.

Design goals
------------
- Postgres-first SQLAlchemy persistence
- Tenant/user/portfolio aware
- No Streamlit dependency
- Graceful no-data behavior
- Compatible with Sprint 25 Phase 3 Quant Research outputs
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from math import isfinite, sqrt
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None  # type: ignore

DEFAULT_FACTOR_SNAPSHOT_TABLE = "forex_factor_model_snapshots"
DEFAULT_FACTOR_EXPOSURE_TABLE = "forex_factor_model_exposures"
DEFAULT_FACTOR_SIGNAL_TABLE = "forex_factor_model_signals"

MAJOR_PAIRS: Tuple[str, ...] = (
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD"
)
CROSS_PAIRS: Tuple[str, ...] = (
    "EURGBP", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "CHFJPY", "EURAUD", "GBPAUD"
)
DEFAULT_PAIRS: Tuple[str, ...] = MAJOR_PAIRS + CROSS_PAIRS

FACTOR_WEIGHTS: Dict[str, float] = {
    "momentum": 0.22,
    "carry": 0.16,
    "value": 0.14,
    "volatility_quality": 0.14,
    "trend": 0.16,
    "liquidity": 0.08,
    "macro": 0.10,
}


@dataclass
class ForexFactorExposure:
    tenant_id: str
    user_id: Optional[str]
    portfolio_id: Optional[str]
    symbol: str
    asof: datetime
    close: Optional[float]
    momentum_20d: Optional[float]
    momentum_60d: Optional[float]
    carry_input: Optional[float]
    value_zscore: Optional[float]
    volatility_20d: Optional[float]
    volatility_60d: Optional[float]
    trend_slope: Optional[float]
    liquidity_proxy: Optional[float]
    macro_input: Optional[float]
    momentum_score: float
    carry_score: float
    value_score: float
    volatility_quality_score: float
    trend_score: float
    liquidity_score: float
    macro_score: float
    composite_factor_score: float
    factor_rank: int
    factor_signal: str
    factor_conviction: str
    rationale: str


@dataclass
class ForexFactorSnapshot:
    tenant_id: str
    user_id: Optional[str]
    portfolio_id: Optional[str]
    asof: datetime
    universe_size: int
    analyzed_pairs: int
    long_candidates: int
    short_candidates: int
    neutral_candidates: int
    avg_factor_score: float
    top_factor_pair: Optional[str]
    bottom_factor_pair: Optional[str]
    dominant_factor: Optional[str]
    factor_regime: str
    model_version: str
    summary: str


@dataclass
class ForexFactorSignal:
    tenant_id: str
    user_id: Optional[str]
    portfolio_id: Optional[str]
    symbol: str
    asof: datetime
    side: str
    conviction: str
    composite_factor_score: float
    suggested_weight: float
    risk_bucket: str
    rationale: str


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        if isinstance(value, str):
            value = value.replace(",", "").replace("%", "").strip()
            if value in {"", "-", "—", "None", "nan"}:
                return None
        out = float(value)
        return out if isfinite(out) else None
    except Exception:
        return None


def _normalize_symbol(symbol: Any) -> str:
    return str(symbol or "").replace("/", "").replace("-", "").replace("_", "").upper().strip()


def _clip(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def _zscore(series: pd.Series, value: Optional[float]) -> Optional[float]:
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


def _score_from_z(z: Optional[float], inverse: bool = False) -> float:
    if z is None or not isfinite(float(z)):
        return 50.0
    z = max(-3.0, min(3.0, float(z)))
    score = 50.0 + z * 16.6667
    if inverse:
        score = 100.0 - score
    return _clip(score)


def _extract_price_frame(market_data: Any, pairs: Optional[Sequence[str]] = None) -> pd.DataFrame:
    wanted = {_normalize_symbol(p) for p in (pairs or DEFAULT_PAIRS)}
    if market_data is None:
        return pd.DataFrame()

    if isinstance(market_data, pd.DataFrame):
        df = market_data.copy()
        cols = {str(c).lower(): c for c in df.columns}
        symbol_col = cols.get("symbol") or cols.get("pair") or cols.get("ticker")
        date_col = cols.get("asof") or cols.get("date") or cols.get("timestamp") or cols.get("datetime")
        close_col = cols.get("close") or cols.get("price") or cols.get("last") or cols.get("rate") or cols.get("mid")
        if symbol_col and close_col:
            if date_col:
                df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            else:
                df["asof"] = utc_now()
                date_col = "asof"
            df[symbol_col] = df[symbol_col].map(_normalize_symbol)
            if wanted:
                df = df[df[symbol_col].isin(wanted)]
            return df.pivot_table(index=date_col, columns=symbol_col, values=close_col, aggfunc="last").sort_index().apply(pd.to_numeric, errors="coerce")
        return df.sort_index().apply(pd.to_numeric, errors="coerce")

    if isinstance(market_data, Mapping):
        frames: List[pd.Series] = []
        for raw_symbol, payload in market_data.items():
            symbol = _normalize_symbol(raw_symbol)
            if wanted and symbol not in wanted:
                continue
            if isinstance(payload, pd.DataFrame):
                cols = {str(c).lower(): c for c in payload.columns}
                close_col = cols.get("close") or cols.get("price") or cols.get("last") or cols.get("rate") or cols.get("mid")
                date_col = cols.get("asof") or cols.get("date") or cols.get("timestamp") or cols.get("datetime")
                if close_col is None:
                    continue
                idx = pd.to_datetime(payload[date_col], errors="coerce") if date_col else pd.RangeIndex(len(payload))
                frames.append(pd.Series(pd.to_numeric(payload[close_col], errors="coerce").values, index=idx, name=symbol))
            elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
                frame = pd.DataFrame(payload)
                if frame.empty:
                    continue
                cols = {str(c).lower(): c for c in frame.columns}
                close_col = cols.get("close") or cols.get("price") or cols.get("last") or cols.get("rate") or cols.get("mid")
                date_col = cols.get("asof") or cols.get("date") or cols.get("timestamp") or cols.get("datetime")
                if close_col is None:
                    continue
                idx = pd.to_datetime(frame[date_col], errors="coerce") if date_col else pd.RangeIndex(len(frame))
                frames.append(pd.Series(pd.to_numeric(frame[close_col], errors="coerce").values, index=idx, name=symbol))
            else:
                px = _safe_float(payload)
                if px is not None:
                    frames.append(pd.Series([px], index=[utc_now()], name=symbol))
        if frames:
            return pd.concat(frames, axis=1).sort_index()
    return pd.DataFrame()


def ensure_forex_factor_model_tables(db: Any) -> None:
    """Create Sprint 25 Phase 4 Postgres-compatible tables and indexes."""
    if db is None:
        return

    ddl_snapshot = f"""
    CREATE TABLE IF NOT EXISTS {DEFAULT_FACTOR_SNAPSHOT_TABLE} (
        id BIGSERIAL PRIMARY KEY,
        tenant_id VARCHAR(100) NOT NULL,
        user_id VARCHAR(100),
        portfolio_id VARCHAR(100),
        asof TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        universe_size INTEGER NOT NULL DEFAULT 0,
        analyzed_pairs INTEGER NOT NULL DEFAULT 0,
        long_candidates INTEGER NOT NULL DEFAULT 0,
        short_candidates INTEGER NOT NULL DEFAULT 0,
        neutral_candidates INTEGER NOT NULL DEFAULT 0,
        avg_factor_score DOUBLE PRECISION,
        top_factor_pair VARCHAR(20),
        bottom_factor_pair VARCHAR(20),
        dominant_factor VARCHAR(50),
        factor_regime VARCHAR(50),
        model_version VARCHAR(50),
        summary TEXT,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """
    ddl_exposure = f"""
    CREATE TABLE IF NOT EXISTS {DEFAULT_FACTOR_EXPOSURE_TABLE} (
        id BIGSERIAL PRIMARY KEY,
        tenant_id VARCHAR(100) NOT NULL,
        user_id VARCHAR(100),
        portfolio_id VARCHAR(100),
        symbol VARCHAR(20) NOT NULL,
        asof TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        close DOUBLE PRECISION,
        momentum_20d DOUBLE PRECISION,
        momentum_60d DOUBLE PRECISION,
        carry_input DOUBLE PRECISION,
        value_zscore DOUBLE PRECISION,
        volatility_20d DOUBLE PRECISION,
        volatility_60d DOUBLE PRECISION,
        trend_slope DOUBLE PRECISION,
        liquidity_proxy DOUBLE PRECISION,
        macro_input DOUBLE PRECISION,
        momentum_score DOUBLE PRECISION,
        carry_score DOUBLE PRECISION,
        value_score DOUBLE PRECISION,
        volatility_quality_score DOUBLE PRECISION,
        trend_score DOUBLE PRECISION,
        liquidity_score DOUBLE PRECISION,
        macro_score DOUBLE PRECISION,
        composite_factor_score DOUBLE PRECISION,
        factor_rank INTEGER,
        factor_signal VARCHAR(30),
        factor_conviction VARCHAR(30),
        rationale TEXT,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """
    ddl_signal = f"""
    CREATE TABLE IF NOT EXISTS {DEFAULT_FACTOR_SIGNAL_TABLE} (
        id BIGSERIAL PRIMARY KEY,
        tenant_id VARCHAR(100) NOT NULL,
        user_id VARCHAR(100),
        portfolio_id VARCHAR(100),
        symbol VARCHAR(20) NOT NULL,
        asof TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        side VARCHAR(20),
        conviction VARCHAR(30),
        composite_factor_score DOUBLE PRECISION,
        suggested_weight DOUBLE PRECISION,
        risk_bucket VARCHAR(40),
        rationale TEXT,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """
    indexes = [
        f"CREATE INDEX IF NOT EXISTS idx_{DEFAULT_FACTOR_SNAPSHOT_TABLE}_tenant_asof ON {DEFAULT_FACTOR_SNAPSHOT_TABLE} (tenant_id, asof DESC);",
        f"CREATE INDEX IF NOT EXISTS idx_{DEFAULT_FACTOR_EXPOSURE_TABLE}_tenant_asof ON {DEFAULT_FACTOR_EXPOSURE_TABLE} (tenant_id, asof DESC);",
        f"CREATE INDEX IF NOT EXISTS idx_{DEFAULT_FACTOR_EXPOSURE_TABLE}_tenant_symbol ON {DEFAULT_FACTOR_EXPOSURE_TABLE} (tenant_id, symbol, asof DESC);",
        f"CREATE INDEX IF NOT EXISTS idx_{DEFAULT_FACTOR_SIGNAL_TABLE}_tenant_asof ON {DEFAULT_FACTOR_SIGNAL_TABLE} (tenant_id, asof DESC);",
    ]
    try:
        db.execute(text(ddl_snapshot))
        db.execute(text(ddl_exposure))
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


class ForexFactorModelsEngine:
    """Live multi-factor model engine with optional Postgres persistence."""

    model_version = "sprint25_phase4_v1"

    def __init__(self, db: Any = None, tenant_id: Optional[str] = None, user_id: Optional[str] = None, portfolio_id: Optional[str] = None):
        self.db = db
        self.tenant_id = str(tenant_id or "default")
        self.user_id = str(user_id) if user_id is not None else None
        self.portfolio_id = str(portfolio_id) if portfolio_id is not None else None

    def run_factor_models(
        self,
        market_data: Any = None,
        pairs: Optional[Sequence[str]] = None,
        carry_inputs: Optional[Mapping[str, Any]] = None,
        macro_inputs: Optional[Mapping[str, Any]] = None,
        liquidity_inputs: Optional[Mapping[str, Any]] = None,
        persist: bool = True,
    ) -> Dict[str, Any]:
        price_frame = _extract_price_frame(market_data, pairs=pairs)
        universe = [_normalize_symbol(p) for p in (pairs or list(price_frame.columns) or DEFAULT_PAIRS)]
        universe = [p for p in universe if p]
        asof = utc_now()

        if price_frame.empty:
            snapshot = ForexFactorSnapshot(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                portfolio_id=self.portfolio_id,
                asof=asof,
                universe_size=len(universe),
                analyzed_pairs=0,
                long_candidates=0,
                short_candidates=0,
                neutral_candidates=0,
                avg_factor_score=0.0,
                top_factor_pair=None,
                bottom_factor_pair=None,
                dominant_factor=None,
                factor_regime="NO_DATA",
                model_version=self.model_version,
                summary="No live forex price data was available for factor model analysis.",
            )
            return {"snapshot": asdict(snapshot), "exposures": [], "signals": [], "data_status": "NO_DATA"}

        price_frame = price_frame.dropna(axis=1, how="all").ffill()
        returns = price_frame.pct_change(fill_method=None)
        latest = price_frame.iloc[-1]

        momentum20_series = price_frame.apply(lambda s: s.dropna().iloc[-1] / s.dropna().iloc[-21] - 1.0 if len(s.dropna()) >= 21 else None)
        momentum60_series = price_frame.apply(lambda s: s.dropna().iloc[-1] / s.dropna().iloc[-61] - 1.0 if len(s.dropna()) >= 61 else None)
        vol20_series = returns.tail(20).std() * sqrt(252) if len(returns) >= 5 else returns.std() * sqrt(252)
        vol60_series = returns.tail(60).std() * sqrt(252) if len(returns) >= 20 else vol20_series

        carry_series = pd.Series({
            _normalize_symbol(k): _safe_float(v)
            for k, v in (carry_inputs or {}).items()
            if _safe_float(v) is not None
        }, dtype="float64")
        macro_series = pd.Series({
            _normalize_symbol(k): _safe_float(v)
            for k, v in (macro_inputs or {}).items()
            if _safe_float(v) is not None
        }, dtype="float64")
        liquidity_series = pd.Series({
            _normalize_symbol(k): _safe_float(v)
            for k, v in (liquidity_inputs or {}).items()
            if _safe_float(v) is not None
        }, dtype="float64")

        exposure_rows: List[ForexFactorExposure] = []
        for symbol in price_frame.columns:
            series = pd.to_numeric(price_frame[symbol], errors="coerce").dropna()
            if series.empty:
                continue

            close = _safe_float(latest.get(symbol))
            mom20 = _safe_float(momentum20_series.get(symbol)) if hasattr(momentum20_series, "get") else None
            mom60 = _safe_float(momentum60_series.get(symbol)) if hasattr(momentum60_series, "get") else None
            vol20 = _safe_float(vol20_series.get(symbol)) if hasattr(vol20_series, "get") else None
            vol60 = _safe_float(vol60_series.get(symbol)) if hasattr(vol60_series, "get") else None

            if len(series) >= 60:
                ma60 = float(series.tail(60).mean())
                std60 = float(series.tail(60).std(ddof=0))
                value_z = ((float(series.iloc[-1]) - ma60) / std60) if std60 > 0 else None
            elif len(series) >= 20:
                ma20 = float(series.tail(20).mean())
                std20 = float(series.tail(20).std(ddof=0))
                value_z = ((float(series.iloc[-1]) - ma20) / std20) if std20 > 0 else None
            else:
                value_z = None

            if len(series) >= 30:
                y = pd.Series(series.tail(30).values, dtype="float64")
                x = pd.Series(range(len(y)), dtype="float64")
                if float(x.std(ddof=0)) > 0 and float(y.std(ddof=0)) > 0:
                    trend_slope = float(y.corr(x))
                else:
                    trend_slope = None
            else:
                trend_slope = None

            carry_input = _safe_float(carry_series.get(symbol)) if not carry_series.empty else None
            macro_input = _safe_float(macro_series.get(symbol)) if not macro_series.empty else None
            liquidity_input = _safe_float(liquidity_series.get(symbol)) if not liquidity_series.empty else None

            momentum_score = _score_from_z(_zscore(momentum20_series, mom20))
            carry_score = _score_from_z(_zscore(carry_series, carry_input)) if not carry_series.empty else 50.0
            value_score = _score_from_z(value_z, inverse=True)
            volatility_quality_score = _score_from_z(_zscore(vol20_series, vol20), inverse=True)
            trend_score = _score_from_z(trend_slope)
            liquidity_score = _score_from_z(_zscore(liquidity_series, liquidity_input)) if not liquidity_series.empty else 50.0
            macro_score = _score_from_z(_zscore(macro_series, macro_input)) if not macro_series.empty else 50.0

            composite = _clip(
                momentum_score * FACTOR_WEIGHTS["momentum"]
                + carry_score * FACTOR_WEIGHTS["carry"]
                + value_score * FACTOR_WEIGHTS["value"]
                + volatility_quality_score * FACTOR_WEIGHTS["volatility_quality"]
                + trend_score * FACTOR_WEIGHTS["trend"]
                + liquidity_score * FACTOR_WEIGHTS["liquidity"]
                + macro_score * FACTOR_WEIGHTS["macro"]
            )

            if composite >= 72:
                factor_signal = "LONG"
                conviction = "HIGH" if composite >= 84 else "MEDIUM"
            elif composite <= 35:
                factor_signal = "SHORT"
                conviction = "HIGH" if composite <= 25 else "MEDIUM"
            else:
                factor_signal = "NEUTRAL"
                conviction = "LOW"

            rationale = (
                f"{symbol} factor score {composite:.1f}: momentum {momentum_score:.1f}, carry {carry_score:.1f}, "
                f"value {value_score:.1f}, volatility quality {volatility_quality_score:.1f}, trend {trend_score:.1f}, "
                f"liquidity {liquidity_score:.1f}, macro {macro_score:.1f}."
            )
            exposure_rows.append(ForexFactorExposure(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                portfolio_id=self.portfolio_id,
                symbol=symbol,
                asof=asof,
                close=close,
                momentum_20d=mom20,
                momentum_60d=mom60,
                carry_input=carry_input,
                value_zscore=_safe_float(value_z),
                volatility_20d=vol20,
                volatility_60d=vol60,
                trend_slope=_safe_float(trend_slope),
                liquidity_proxy=liquidity_input,
                macro_input=macro_input,
                momentum_score=float(momentum_score),
                carry_score=float(carry_score),
                value_score=float(value_score),
                volatility_quality_score=float(volatility_quality_score),
                trend_score=float(trend_score),
                liquidity_score=float(liquidity_score),
                macro_score=float(macro_score),
                composite_factor_score=float(composite),
                factor_rank=0,
                factor_signal=factor_signal,
                factor_conviction=conviction,
                rationale=rationale,
            ))

        exposure_rows = sorted(exposure_rows, key=lambda x: x.composite_factor_score, reverse=True)
        for idx, row in enumerate(exposure_rows, start=1):
            row.factor_rank = idx

        signals = self._build_factor_signals(exposure_rows, asof=asof)
        long_count = sum(1 for e in exposure_rows if e.factor_signal == "LONG")
        short_count = sum(1 for e in exposure_rows if e.factor_signal == "SHORT")
        neutral_count = sum(1 for e in exposure_rows if e.factor_signal == "NEUTRAL")
        avg_score = float(sum(e.composite_factor_score for e in exposure_rows) / len(exposure_rows)) if exposure_rows else 0.0
        top_pair = exposure_rows[0].symbol if exposure_rows else None
        bottom_pair = exposure_rows[-1].symbol if exposure_rows else None
        dominant_factor = self._dominant_factor(exposure_rows)
        factor_regime = self._factor_regime(exposure_rows)
        summary = (
            f"Factor model analyzed {len(exposure_rows)} forex pairs. Average score {avg_score:.1f}; "
            f"top pair {top_pair or 'N/A'}; bottom pair {bottom_pair or 'N/A'}; dominant factor {dominant_factor or 'N/A'}; regime {factor_regime}."
        )
        snapshot = ForexFactorSnapshot(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,
            asof=asof,
            universe_size=len(universe),
            analyzed_pairs=len(exposure_rows),
            long_candidates=long_count,
            short_candidates=short_count,
            neutral_candidates=neutral_count,
            avg_factor_score=avg_score,
            top_factor_pair=top_pair,
            bottom_factor_pair=bottom_pair,
            dominant_factor=dominant_factor,
            factor_regime=factor_regime,
            model_version=self.model_version,
            summary=summary,
        )
        result = {
            "snapshot": asdict(snapshot),
            "exposures": [asdict(e) for e in exposure_rows],
            "signals": [asdict(s) for s in signals],
            "factor_weights": dict(FACTOR_WEIGHTS),
            "data_status": "LIVE_INPUT_ANALYZED",
        }
        if persist and self.db is not None:
            self.persist_result(result)
        return result

    def _build_factor_signals(self, exposures: Sequence[ForexFactorExposure], asof: datetime) -> List[ForexFactorSignal]:
        selected = [e for e in exposures if e.factor_signal in {"LONG", "SHORT"}]
        if not selected:
            return []
        total_edge = sum(abs(e.composite_factor_score - 50.0) for e in selected) or 1.0
        signals: List[ForexFactorSignal] = []
        for e in selected:
            edge = abs(e.composite_factor_score - 50.0)
            side = "BUY" if e.factor_signal == "LONG" else "SELL"
            weight = round(min(0.20, max(0.01, edge / total_edge)), 4)
            vol = e.volatility_20d or e.volatility_60d or 0.0
            risk_bucket = "HIGH_VOL" if vol >= 0.18 else "NORMAL_VOL" if vol > 0 else "UNKNOWN_VOL"
            signals.append(ForexFactorSignal(
                tenant_id=e.tenant_id,
                user_id=e.user_id,
                portfolio_id=e.portfolio_id,
                symbol=e.symbol,
                asof=asof,
                side=side,
                conviction=e.factor_conviction,
                composite_factor_score=e.composite_factor_score,
                suggested_weight=weight,
                risk_bucket=risk_bucket,
                rationale=f"{side} {e.symbol}: {e.rationale}",
            ))
        return signals

    def _dominant_factor(self, exposures: Sequence[ForexFactorExposure]) -> Optional[str]:
        if not exposures:
            return None
        factor_values = {
            "momentum": [e.momentum_score for e in exposures],
            "carry": [e.carry_score for e in exposures],
            "value": [e.value_score for e in exposures],
            "volatility_quality": [e.volatility_quality_score for e in exposures],
            "trend": [e.trend_score for e in exposures],
            "liquidity": [e.liquidity_score for e in exposures],
            "macro": [e.macro_score for e in exposures],
        }
        dispersion = {k: float(pd.Series(v).std(ddof=0)) for k, v in factor_values.items()}
        return max(dispersion, key=dispersion.get) if dispersion else None

    def _factor_regime(self, exposures: Sequence[ForexFactorExposure]) -> str:
        if not exposures:
            return "NO_DATA"
        avg_vol_score = sum(e.volatility_quality_score for e in exposures) / len(exposures)
        avg_trend = sum(e.trend_score for e in exposures) / len(exposures)
        if avg_vol_score < 40:
            return "RISK_OFF_HIGH_VOL"
        if avg_trend > 60:
            return "TREND_FOLLOWING"
        if avg_trend < 42:
            return "MEAN_REVERSION"
        return "BALANCED_FACTOR_REGIME"

    def persist_result(self, result: Mapping[str, Any]) -> None:
        if self.db is None:
            return
        ensure_forex_factor_model_tables(self.db)
        snapshot = dict(result.get("snapshot") or {})
        exposures = list(result.get("exposures") or [])
        signals = list(result.get("signals") or [])
        try:
            self.db.execute(text(f"""
                INSERT INTO {DEFAULT_FACTOR_SNAPSHOT_TABLE} (
                    tenant_id, user_id, portfolio_id, asof, universe_size, analyzed_pairs,
                    long_candidates, short_candidates, neutral_candidates, avg_factor_score,
                    top_factor_pair, bottom_factor_pair, dominant_factor, factor_regime,
                    model_version, summary
                ) VALUES (
                    :tenant_id, :user_id, :portfolio_id, :asof, :universe_size, :analyzed_pairs,
                    :long_candidates, :short_candidates, :neutral_candidates, :avg_factor_score,
                    :top_factor_pair, :bottom_factor_pair, :dominant_factor, :factor_regime,
                    :model_version, :summary
                )
            """), snapshot)
            for row in exposures:
                self.db.execute(text(f"""
                    INSERT INTO {DEFAULT_FACTOR_EXPOSURE_TABLE} (
                        tenant_id, user_id, portfolio_id, symbol, asof, close,
                        momentum_20d, momentum_60d, carry_input, value_zscore,
                        volatility_20d, volatility_60d, trend_slope, liquidity_proxy, macro_input,
                        momentum_score, carry_score, value_score, volatility_quality_score,
                        trend_score, liquidity_score, macro_score, composite_factor_score,
                        factor_rank, factor_signal, factor_conviction, rationale
                    ) VALUES (
                        :tenant_id, :user_id, :portfolio_id, :symbol, :asof, :close,
                        :momentum_20d, :momentum_60d, :carry_input, :value_zscore,
                        :volatility_20d, :volatility_60d, :trend_slope, :liquidity_proxy, :macro_input,
                        :momentum_score, :carry_score, :value_score, :volatility_quality_score,
                        :trend_score, :liquidity_score, :macro_score, :composite_factor_score,
                        :factor_rank, :factor_signal, :factor_conviction, :rationale
                    )
                """), row)
            for row in signals:
                self.db.execute(text(f"""
                    INSERT INTO {DEFAULT_FACTOR_SIGNAL_TABLE} (
                        tenant_id, user_id, portfolio_id, symbol, asof, side, conviction,
                        composite_factor_score, suggested_weight, risk_bucket, rationale
                    ) VALUES (
                        :tenant_id, :user_id, :portfolio_id, :symbol, :asof, :side, :conviction,
                        :composite_factor_score, :suggested_weight, :risk_bucket, :rationale
                    )
                """), row)
            self.db.commit()
        except SQLAlchemyError:
            try:
                self.db.rollback()
            except Exception:
                pass
            raise

    def load_latest(self, limit: int = 100) -> Dict[str, Any]:
        if self.db is None:
            return {"snapshot": None, "exposures": [], "signals": [], "data_status": "NO_DB_SESSION"}
        ensure_forex_factor_model_tables(self.db)
        snapshot = None
        exposures: List[Dict[str, Any]] = []
        signals: List[Dict[str, Any]] = []
        snap_rows = self.db.execute(text(f"""
            SELECT * FROM {DEFAULT_FACTOR_SNAPSHOT_TABLE}
            WHERE tenant_id = :tenant_id
            ORDER BY asof DESC, id DESC
            LIMIT 1
        """), {"tenant_id": self.tenant_id}).mappings().all()
        if snap_rows:
            snapshot = dict(snap_rows[0])
            asof = snapshot.get("asof")
            exposure_rows = self.db.execute(text(f"""
                SELECT * FROM {DEFAULT_FACTOR_EXPOSURE_TABLE}
                WHERE tenant_id = :tenant_id AND asof = :asof
                ORDER BY factor_rank ASC NULLS LAST, composite_factor_score DESC NULLS LAST
                LIMIT :limit
            """), {"tenant_id": self.tenant_id, "asof": asof, "limit": int(limit)}).mappings().all()
            signal_rows = self.db.execute(text(f"""
                SELECT * FROM {DEFAULT_FACTOR_SIGNAL_TABLE}
                WHERE tenant_id = :tenant_id AND asof = :asof
                ORDER BY ABS(composite_factor_score - 50.0) DESC NULLS LAST, symbol ASC
                LIMIT :limit
            """), {"tenant_id": self.tenant_id, "asof": asof, "limit": int(limit)}).mappings().all()
            exposures = [dict(r) for r in exposure_rows]
            signals = [dict(r) for r in signal_rows]
        return {"snapshot": snapshot, "exposures": exposures, "signals": signals, "data_status": "DB_LATEST" if snapshot else "DB_EMPTY"}


def run_forex_factor_models(
    market_data: Any = None,
    db: Any = None,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    pairs: Optional[Sequence[str]] = None,
    carry_inputs: Optional[Mapping[str, Any]] = None,
    macro_inputs: Optional[Mapping[str, Any]] = None,
    liquidity_inputs: Optional[Mapping[str, Any]] = None,
    persist: bool = True,
) -> Dict[str, Any]:
    return ForexFactorModelsEngine(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
    ).run_factor_models(
        market_data=market_data,
        pairs=pairs,
        carry_inputs=carry_inputs,
        macro_inputs=macro_inputs,
        liquidity_inputs=liquidity_inputs,
        persist=persist,
    )
