# modules/forex/forex_macro_engine.py

from __future__ import annotations

import json
import logging
import math
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    from modules.forex.forex_service import (
        ForexService,
        get_forex_service,
        normalize_pair,
        split_pair,
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )
except Exception:
    from forex_service import (
        ForexService,
        get_forex_service,
        normalize_pair,
        split_pair,
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )


logger = logging.getLogger(__name__)

DEFAULT_MACRO_PAIRS = MAJOR_PAIRS + CROSS_PAIRS

CENTRAL_BANKS = {
    "USD": "Federal Reserve",
    "EUR": "European Central Bank",
    "GBP": "Bank of England",
    "JPY": "Bank of Japan",
    "CHF": "Swiss National Bank",
    "AUD": "Reserve Bank of Australia",
    "CAD": "Bank of Canada",
    "NZD": "Reserve Bank of New Zealand",
}

POLICY_RATE_PROXY = {
    "USD": 5.25,
    "EUR": 4.00,
    "GBP": 5.25,
    "JPY": 0.10,
    "CHF": 1.50,
    "AUD": 4.35,
    "CAD": 5.00,
    "NZD": 5.50,
}

INFLATION_PROXY = {
    "USD": 3.2,
    "EUR": 2.8,
    "GBP": 3.9,
    "JPY": 2.7,
    "CHF": 1.7,
    "AUD": 4.1,
    "CAD": 3.1,
    "NZD": 4.7,
}

GROWTH_PROXY = {
    "USD": 72.0,
    "EUR": 54.0,
    "GBP": 56.0,
    "JPY": 48.0,
    "CHF": 58.0,
    "AUD": 62.0,
    "CAD": 61.0,
    "NZD": 59.0,
}

RISK_SENSITIVITY = {
    "USD": 68.0,
    "JPY": 82.0,
    "CHF": 78.0,
    "EUR": 55.0,
    "GBP": 57.0,
    "CAD": 61.0,
    "AUD": 72.0,
    "NZD": 74.0,
}

COMMODITY_SENSITIVITY = {
    "AUD": 80.0,
    "CAD": 76.0,
    "NZD": 70.0,
    "USD": 50.0,
    "EUR": 42.0,
    "GBP": 45.0,
    "JPY": 35.0,
    "CHF": 38.0,
}


@dataclass
class ForexMacroSnapshot:
    macro_id: str
    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]
    pair: str
    base_currency: str
    quote_currency: str
    base_central_bank: str
    quote_central_bank: str
    base_policy_rate: float
    quote_policy_rate: float
    rate_differential: float
    base_inflation: float
    quote_inflation: float
    inflation_differential: float
    base_growth_score: float
    quote_growth_score: float
    growth_differential: float
    usd_strength_score: float
    risk_regime_score: float
    risk_on_score: float
    risk_off_score: float
    commodity_signal: float
    yield_signal: float
    central_bank_bias: str
    macro_direction: str
    macro_recommendation: str
    macro_score: float
    confidence_score: float
    notes: str
    asof: datetime
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["asof"] = self.asof.isoformat()
        return data


@dataclass
class ForexMacroScan:
    scan_id: str
    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]
    pair_count: int
    avg_macro_score: float
    avg_confidence_score: float
    bullish_count: int
    bearish_count: int
    neutral_count: int
    top_bullish_pair: Optional[str]
    top_bearish_pair: Optional[str]
    created_at: datetime
    snapshots: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _naive(dt: datetime) -> datetime:
    return dt.replace(tzinfo=None)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        result = float(value)
        if math.isnan(result) or math.isinf(result):
            return default
        return result
    except Exception:
        return default


def _round(value: Any, places: int = 2) -> float:
    return round(_safe_float(value), places)


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def _json(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, default=str))
    except Exception:
        return {"value": str(value)}


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return getattr(row, key)
    except Exception:
        return default


class ForexMacroEngine:
    """
    Institutional Forex macro intelligence engine.

    Measures:
    - Central bank bias
    - Rate differential
    - Inflation differential
    - Growth differential
    - USD strength proxy
    - Risk-on / risk-off overlay
    - Commodity sensitivity
    - Yield signal
    - Macro direction
    - Macro recommendation

    Architecture:
    - Explicit state passing
    - Tenant-safe
    - Neon Postgres compatible
    - No global runtime state
    """

    def __init__(
        self,
        *,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        db: Any = None,
        forex_service: Optional[ForexService] = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.portfolio_id = portfolio_id
        self.db = db
        self.forex_service = forex_service or get_forex_service(
            tenant_id=tenant_id,
            user_id=user_id,
            db=db,
        )

    def ensure_tables(self) -> None:
        if self.db is None:
            return

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS forex_macro_snapshots (
                macro_id VARCHAR(80) PRIMARY KEY,
                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),
                pair VARCHAR(20),
                base_currency VARCHAR(3),
                quote_currency VARCHAR(3),
                base_central_bank VARCHAR(120),
                quote_central_bank VARCHAR(120),
                base_policy_rate DOUBLE PRECISION,
                quote_policy_rate DOUBLE PRECISION,
                rate_differential DOUBLE PRECISION,
                base_inflation DOUBLE PRECISION,
                quote_inflation DOUBLE PRECISION,
                inflation_differential DOUBLE PRECISION,
                base_growth_score DOUBLE PRECISION,
                quote_growth_score DOUBLE PRECISION,
                growth_differential DOUBLE PRECISION,
                usd_strength_score DOUBLE PRECISION,
                risk_regime_score DOUBLE PRECISION,
                risk_on_score DOUBLE PRECISION,
                risk_off_score DOUBLE PRECISION,
                commodity_signal DOUBLE PRECISION,
                yield_signal DOUBLE PRECISION,
                central_bank_bias VARCHAR(80),
                macro_direction VARCHAR(40),
                macro_recommendation VARCHAR(40),
                macro_score DOUBLE PRECISION,
                confidence_score DOUBLE PRECISION,
                notes TEXT,
                raw_payload JSONB,
                asof TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_forex_macro_snapshots_tenant_pair_asof
            ON forex_macro_snapshots (tenant_id, pair, asof DESC)
            """
        )

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS forex_macro_scans (
                scan_id VARCHAR(80) PRIMARY KEY,
                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),
                pair_count INTEGER,
                avg_macro_score DOUBLE PRECISION,
                avg_confidence_score DOUBLE PRECISION,
                bullish_count INTEGER,
                bearish_count INTEGER,
                neutral_count INTEGER,
                top_bullish_pair VARCHAR(20),
                top_bearish_pair VARCHAR(20),
                payload JSONB,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        if hasattr(self.db, "commit"):
            self.db.commit()

    def analyze_pair(
        self,
        pair: str,
        *,
        save: bool = True,
        macro_overrides: Optional[Dict[str, Any]] = None,
    ) -> ForexMacroSnapshot:
        normalized_pair = normalize_pair(pair)
        base, quote = split_pair(normalized_pair)

        snapshot = self._build_snapshot(
            pair=normalized_pair,
            base=base,
            quote=quote,
            macro_overrides=macro_overrides or {},
        )

        if save:
            self.save_snapshot(snapshot)

        return snapshot

    def scan_pairs(
        self,
        pairs: Optional[List[str]] = None,
        *,
        save: bool = True,
        macro_overrides: Optional[Dict[str, Any]] = None,
    ) -> ForexMacroScan:
        selected_pairs = pairs or DEFAULT_MACRO_PAIRS
        snapshots: List[ForexMacroSnapshot] = []

        for pair in selected_pairs:
            try:
                snapshots.append(
                    self.analyze_pair(
                        pair,
                        save=save,
                        macro_overrides=macro_overrides,
                    )
                )
            except Exception as exc:
                logger.warning("Failed to analyze Forex macro for %s: %s", pair, exc)

        scan = self._build_scan(
            pair_count=len(selected_pairs),
            snapshots=snapshots,
        )

        if save:
            self.save_scan(scan)

        return scan

    def rank_macro_pairs(
        self,
        pairs: Optional[List[str]] = None,
        *,
        direction: str = "BULLISH",
        limit: Optional[int] = None,
        save: bool = False,
    ) -> List[ForexMacroSnapshot]:
        scan = self.scan_pairs(
            pairs=pairs,
            save=save,
        )

        snapshots = [
            self._snapshot_from_dict(row)
            for row in scan.snapshots
        ]

        if direction.upper() == "BEARISH":
            ranked = sorted(
                snapshots,
                key=lambda item: (
                    item.macro_score,
                    item.confidence_score,
                ),
            )
        else:
            ranked = sorted(
                snapshots,
                key=lambda item: (
                    item.macro_score,
                    item.confidence_score,
                ),
                reverse=True,
            )

        if limit:
            return ranked[: int(limit)]

        return ranked

    def save_snapshot(
        self,
        snapshot: ForexMacroSnapshot,
    ) -> None:
        if self.db is None:
            return

        self.ensure_tables()

        self.db.execute(
            """
            INSERT INTO forex_macro_snapshots (
                macro_id,
                tenant_id,
                user_id,
                portfolio_id,
                pair,
                base_currency,
                quote_currency,
                base_central_bank,
                quote_central_bank,
                base_policy_rate,
                quote_policy_rate,
                rate_differential,
                base_inflation,
                quote_inflation,
                inflation_differential,
                base_growth_score,
                quote_growth_score,
                growth_differential,
                usd_strength_score,
                risk_regime_score,
                risk_on_score,
                risk_off_score,
                commodity_signal,
                yield_signal,
                central_bank_bias,
                macro_direction,
                macro_recommendation,
                macro_score,
                confidence_score,
                notes,
                raw_payload,
                asof
            )
            VALUES (
                :macro_id,
                :tenant_id,
                :user_id,
                :portfolio_id,
                :pair,
                :base_currency,
                :quote_currency,
                :base_central_bank,
                :quote_central_bank,
                :base_policy_rate,
                :quote_policy_rate,
                :rate_differential,
                :base_inflation,
                :quote_inflation,
                :inflation_differential,
                :base_growth_score,
                :quote_growth_score,
                :growth_differential,
                :usd_strength_score,
                :risk_regime_score,
                :risk_on_score,
                :risk_off_score,
                :commodity_signal,
                :yield_signal,
                :central_bank_bias,
                :macro_direction,
                :macro_recommendation,
                :macro_score,
                :confidence_score,
                :notes,
                :raw_payload,
                :asof
            )
            ON CONFLICT (macro_id)
            DO UPDATE SET
                base_policy_rate = EXCLUDED.base_policy_rate,
                quote_policy_rate = EXCLUDED.quote_policy_rate,
                rate_differential = EXCLUDED.rate_differential,
                base_inflation = EXCLUDED.base_inflation,
                quote_inflation = EXCLUDED.quote_inflation,
                inflation_differential = EXCLUDED.inflation_differential,
                base_growth_score = EXCLUDED.base_growth_score,
                quote_growth_score = EXCLUDED.quote_growth_score,
                growth_differential = EXCLUDED.growth_differential,
                usd_strength_score = EXCLUDED.usd_strength_score,
                risk_regime_score = EXCLUDED.risk_regime_score,
                risk_on_score = EXCLUDED.risk_on_score,
                risk_off_score = EXCLUDED.risk_off_score,
                commodity_signal = EXCLUDED.commodity_signal,
                yield_signal = EXCLUDED.yield_signal,
                central_bank_bias = EXCLUDED.central_bank_bias,
                macro_direction = EXCLUDED.macro_direction,
                macro_recommendation = EXCLUDED.macro_recommendation,
                macro_score = EXCLUDED.macro_score,
                confidence_score = EXCLUDED.confidence_score,
                notes = EXCLUDED.notes,
                raw_payload = EXCLUDED.raw_payload,
                asof = EXCLUDED.asof
            """,
            {
                **snapshot.to_dict(),
                "raw_payload": _json(snapshot.raw),
                "asof": _naive(snapshot.asof),
            },
        )

        if hasattr(self.db, "commit"):
            self.db.commit()

    def save_scan(
        self,
        scan: ForexMacroScan,
    ) -> None:
        if self.db is None:
            return

        self.ensure_tables()

        self.db.execute(
            """
            INSERT INTO forex_macro_scans (
                scan_id,
                tenant_id,
                user_id,
                portfolio_id,
                pair_count,
                avg_macro_score,
                avg_confidence_score,
                bullish_count,
                bearish_count,
                neutral_count,
                top_bullish_pair,
                top_bearish_pair,
                payload,
                created_at
            )
            VALUES (
                :scan_id,
                :tenant_id,
                :user_id,
                :portfolio_id,
                :pair_count,
                :avg_macro_score,
                :avg_confidence_score,
                :bullish_count,
                :bearish_count,
                :neutral_count,
                :top_bullish_pair,
                :top_bearish_pair,
                :payload,
                :created_at
            )
            ON CONFLICT (scan_id) DO NOTHING
            """,
            {
                **scan.to_dict(),
                "payload": _json(scan.to_dict()),
                "created_at": _naive(scan.created_at),
            },
        )

        if hasattr(self.db, "commit"):
            self.db.commit()

    def load_snapshots(
        self,
        *,
        pair: Optional[str] = None,
        direction: str = "ALL",
        recommendation: str = "ALL",
        limit: int = 250,
    ) -> List[Dict[str, Any]]:
        if self.db is None:
            return []

        self.ensure_tables()

        params: Dict[str, Any] = {
            "tenant_id": self.tenant_id,
            "limit": int(limit),
        }
        where = "tenant_id = :tenant_id"

        if pair:
            where += " AND pair = :pair"
            params["pair"] = normalize_pair(pair)

        if direction and direction.upper() != "ALL":
            where += " AND macro_direction = :direction"
            params["direction"] = direction.upper()

        if recommendation and recommendation.upper() != "ALL":
            where += " AND macro_recommendation = :recommendation"
            params["recommendation"] = recommendation.upper()

        rows = self.db.execute(
            f"""
            SELECT *
            FROM forex_macro_snapshots
            WHERE {where}
            ORDER BY asof DESC
            LIMIT :limit
            """,
            params,
        ).fetchall()

        return [self._row_to_snapshot_dict(row) for row in rows]

    def load_scans(
        self,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        if self.db is None:
            return []

        self.ensure_tables()

        rows = self.db.execute(
            """
            SELECT *
            FROM forex_macro_scans
            WHERE tenant_id = :tenant_id
            ORDER BY created_at DESC
            LIMIT :limit
            """,
            {
                "tenant_id": self.tenant_id,
                "limit": int(limit),
            },
        ).fetchall()

        return [
            {
                "scan_id": _row_get(row, "scan_id"),
                "pair_count": _row_get(row, "pair_count"),
                "avg_macro_score": _row_get(row, "avg_macro_score"),
                "avg_confidence_score": _row_get(row, "avg_confidence_score"),
                "bullish_count": _row_get(row, "bullish_count"),
                "bearish_count": _row_get(row, "bearish_count"),
                "neutral_count": _row_get(row, "neutral_count"),
                "top_bullish_pair": _row_get(row, "top_bullish_pair"),
                "top_bearish_pair": _row_get(row, "top_bearish_pair"),
                "created_at": str(_row_get(row, "created_at", "")),
            }
            for row in rows
        ]

    def _build_snapshot(
        self,
        *,
        pair: str,
        base: str,
        quote: str,
        macro_overrides: Dict[str, Any],
    ) -> ForexMacroSnapshot:
        base_rate = self._macro_value(
            macro_overrides,
            "policy_rate",
            base,
            POLICY_RATE_PROXY.get(base, 2.0),
        )
        quote_rate = self._macro_value(
            macro_overrides,
            "policy_rate",
            quote,
            POLICY_RATE_PROXY.get(quote, 2.0),
        )
        rate_diff = base_rate - quote_rate

        base_inflation = self._macro_value(
            macro_overrides,
            "inflation",
            base,
            INFLATION_PROXY.get(base, 3.0),
        )
        quote_inflation = self._macro_value(
            macro_overrides,
            "inflation",
            quote,
            INFLATION_PROXY.get(quote, 3.0),
        )
        inflation_diff = base_inflation - quote_inflation

        base_growth = self._macro_value(
            macro_overrides,
            "growth_score",
            base,
            GROWTH_PROXY.get(base, 55.0),
        )
        quote_growth = self._macro_value(
            macro_overrides,
            "growth_score",
            quote,
            GROWTH_PROXY.get(quote, 55.0),
        )
        growth_diff = base_growth - quote_growth

        usd_strength = self._usd_strength_score(base, quote, macro_overrides)
        risk_regime = _safe_float(macro_overrides.get("risk_regime_score"), 55.0)

        risk_on_score = self._risk_on_score(
            base=base,
            quote=quote,
            risk_regime=risk_regime,
        )

        risk_off_score = self._risk_off_score(
            base=base,
            quote=quote,
            risk_regime=risk_regime,
        )

        commodity_signal = self._commodity_signal(base, quote)

        yield_signal = self._yield_signal(rate_diff)

        central_bank_bias = self._central_bank_bias(
            rate_diff=rate_diff,
            inflation_diff=inflation_diff,
            growth_diff=growth_diff,
        )

        macro_score = self._macro_score(
            rate_diff=rate_diff,
            inflation_diff=inflation_diff,
            growth_diff=growth_diff,
            usd_strength=usd_strength,
            risk_on_score=risk_on_score,
            risk_off_score=risk_off_score,
            commodity_signal=commodity_signal,
            yield_signal=yield_signal,
            base=base,
            quote=quote,
        )

        direction = self._macro_direction(macro_score)
        recommendation = self._macro_recommendation(macro_score)
        confidence = self._confidence_score(
            macro_score=macro_score,
            rate_diff=rate_diff,
            growth_diff=growth_diff,
            risk_on_score=risk_on_score,
            risk_off_score=risk_off_score,
        )

        notes = self._notes(
            pair=pair,
            rate_diff=rate_diff,
            inflation_diff=inflation_diff,
            growth_diff=growth_diff,
            macro_score=macro_score,
            direction=direction,
            recommendation=recommendation,
        )

        return ForexMacroSnapshot(
            macro_id=str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,
            pair=pair,
            base_currency=base,
            quote_currency=quote,
            base_central_bank=CENTRAL_BANKS.get(base, "Unknown Central Bank"),
            quote_central_bank=CENTRAL_BANKS.get(quote, "Unknown Central Bank"),
            base_policy_rate=_round(base_rate),
            quote_policy_rate=_round(quote_rate),
            rate_differential=_round(rate_diff),
            base_inflation=_round(base_inflation),
            quote_inflation=_round(quote_inflation),
            inflation_differential=_round(inflation_diff),
            base_growth_score=_round(base_growth),
            quote_growth_score=_round(quote_growth),
            growth_differential=_round(growth_diff),
            usd_strength_score=_round(usd_strength),
            risk_regime_score=_round(risk_regime),
            risk_on_score=_round(risk_on_score),
            risk_off_score=_round(risk_off_score),
            commodity_signal=_round(commodity_signal),
            yield_signal=_round(yield_signal),
            central_bank_bias=central_bank_bias,
            macro_direction=direction,
            macro_recommendation=recommendation,
            macro_score=_round(macro_score),
            confidence_score=_round(confidence),
            notes=notes,
            asof=_utc_now(),
            raw={
                "macro_overrides": macro_overrides,
                "policy_rate_proxy": {
                    base: base_rate,
                    quote: quote_rate,
                },
                "inflation_proxy": {
                    base: base_inflation,
                    quote: quote_inflation,
                },
                "growth_proxy": {
                    base: base_growth,
                    quote: quote_growth,
                },
            },
        )

    def _build_scan(
        self,
        *,
        pair_count: int,
        snapshots: List[ForexMacroSnapshot],
    ) -> ForexMacroScan:
        avg_macro = (
            sum(s.macro_score for s in snapshots) / len(snapshots)
            if snapshots
            else 0.0
        )
        avg_confidence = (
            sum(s.confidence_score for s in snapshots) / len(snapshots)
            if snapshots
            else 0.0
        )

        bullish = [
            s for s in snapshots
            if s.macro_direction == "BULLISH"
        ]
        bearish = [
            s for s in snapshots
            if s.macro_direction == "BEARISH"
        ]
        neutral = [
            s for s in snapshots
            if s.macro_direction == "NEUTRAL"
        ]

        top_bullish = (
            sorted(
                bullish,
                key=lambda s: (s.macro_score, s.confidence_score),
                reverse=True,
            )[0].pair
            if bullish
            else None
        )

        top_bearish = (
            sorted(
                bearish,
                key=lambda s: (s.macro_score, s.confidence_score),
            )[0].pair
            if bearish
            else None
        )

        ranked = sorted(
            snapshots,
            key=lambda s: (
                abs(s.macro_score - 50.0),
                s.confidence_score,
            ),
            reverse=True,
        )

        return ForexMacroScan(
            scan_id=str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,
            pair_count=pair_count,
            avg_macro_score=_round(avg_macro),
            avg_confidence_score=_round(avg_confidence),
            bullish_count=len(bullish),
            bearish_count=len(bearish),
            neutral_count=len(neutral),
            top_bullish_pair=top_bullish,
            top_bearish_pair=top_bearish,
            created_at=_utc_now(),
            snapshots=[s.to_dict() for s in ranked],
        )

    def _macro_value(
        self,
        overrides: Dict[str, Any],
        category: str,
        currency: str,
        default: float,
    ) -> float:
        category_values = overrides.get(category, {})

        if isinstance(category_values, dict):
            return _safe_float(category_values.get(currency), default)

        return default

    def _usd_strength_score(
        self,
        base: str,
        quote: str,
        overrides: Dict[str, Any],
    ) -> float:
        base_usd_strength = _safe_float(overrides.get("usd_strength_score"), 62.0)

        if base == "USD":
            return _clamp(base_usd_strength)

        if quote == "USD":
            return _clamp(100.0 - base_usd_strength)

        return 50.0

    def _risk_on_score(
        self,
        *,
        base: str,
        quote: str,
        risk_regime: float,
    ) -> float:
        base_sensitivity = RISK_SENSITIVITY.get(base, 55.0)
        quote_sensitivity = RISK_SENSITIVITY.get(quote, 55.0)

        sensitivity_diff = base_sensitivity - quote_sensitivity

        if risk_regime >= 50:
            return _clamp(50.0 + sensitivity_diff * 0.45)

        return _clamp(50.0 - sensitivity_diff * 0.30)

    def _risk_off_score(
        self,
        *,
        base: str,
        quote: str,
        risk_regime: float,
    ) -> float:
        safe_havens = {
            "USD": 75.0,
            "JPY": 90.0,
            "CHF": 88.0,
        }

        base_safe = safe_havens.get(base, 45.0)
        quote_safe = safe_havens.get(quote, 45.0)

        if risk_regime < 50:
            return _clamp(50.0 + (base_safe - quote_safe) * 0.50)

        return _clamp(50.0 + (base_safe - quote_safe) * 0.20)

    def _commodity_signal(
        self,
        base: str,
        quote: str,
    ) -> float:
        base_signal = COMMODITY_SENSITIVITY.get(base, 50.0)
        quote_signal = COMMODITY_SENSITIVITY.get(quote, 50.0)

        return _clamp(50.0 + (base_signal - quote_signal) * 0.45)

    def _yield_signal(
        self,
        rate_diff: float,
    ) -> float:
        return _clamp(50.0 + rate_diff * 7.5)

    def _central_bank_bias(
        self,
        *,
        rate_diff: float,
        inflation_diff: float,
        growth_diff: float,
    ) -> str:
        score = rate_diff * 2.0 + inflation_diff * 0.75 + growth_diff * 0.05

        if score >= 3:
            return "BASE_HAWKISH"

        if score <= -3:
            return "QUOTE_HAWKISH"

        if score >= 1:
            return "MILD_BASE_HAWKISH"

        if score <= -1:
            return "MILD_QUOTE_HAWKISH"

        return "BALANCED"

    def _macro_score(
        self,
        *,
        rate_diff: float,
        inflation_diff: float,
        growth_diff: float,
        usd_strength: float,
        risk_on_score: float,
        risk_off_score: float,
        commodity_signal: float,
        yield_signal: float,
        base: str,
        quote: str,
    ) -> float:
        rate_component = _clamp(50.0 + rate_diff * 7.0)
        inflation_component = _clamp(50.0 + inflation_diff * 3.0)
        growth_component = _clamp(50.0 + growth_diff * 0.65)

        usd_component = usd_strength

        if base != "USD" and quote != "USD":
            usd_component = 50.0

        score = (
            rate_component * 0.22
            + inflation_component * 0.10
            + growth_component * 0.16
            + usd_component * 0.16
            + risk_on_score * 0.12
            + risk_off_score * 0.08
            + commodity_signal * 0.08
            + yield_signal * 0.08
        )

        return _clamp(score)

    def _macro_direction(
        self,
        macro_score: float,
    ) -> str:
        if macro_score >= 58:
            return "BULLISH"

        if macro_score <= 42:
            return "BEARISH"

        return "NEUTRAL"

    def _macro_recommendation(
        self,
        macro_score: float,
    ) -> str:
        if macro_score >= 72:
            return "STRONG_BUY"

        if macro_score >= 58:
            return "BUY"

        if macro_score <= 28:
            return "STRONG_SELL"

        if macro_score <= 42:
            return "SELL"

        return "WATCH"

    def _confidence_score(
        self,
        *,
        macro_score: float,
        rate_diff: float,
        growth_diff: float,
        risk_on_score: float,
        risk_off_score: float,
    ) -> float:
        score_distance = abs(macro_score - 50.0) * 1.5
        rate_strength = min(25.0, abs(rate_diff) * 4.0)
        growth_strength = min(20.0, abs(growth_diff) * 0.25)
        risk_strength = min(20.0, abs(risk_on_score - risk_off_score) * 0.25)

        confidence = 45.0 + score_distance + rate_strength + growth_strength + risk_strength

        return _clamp(confidence)

    def _notes(
        self,
        *,
        pair: str,
        rate_diff: float,
        inflation_diff: float,
        growth_diff: float,
        macro_score: float,
        direction: str,
        recommendation: str,
    ) -> str:
        notes: List[str] = []

        notes.append(
            f"{pair} macro direction is {direction} with {recommendation} macro recommendation."
        )

        if abs(rate_diff) >= 2:
            notes.append("Rate differential is a meaningful driver.")

        if abs(inflation_diff) >= 1.5:
            notes.append("Inflation differential is elevated.")

        if abs(growth_diff) >= 12:
            notes.append("Growth differential is significant.")

        if 45 <= macro_score <= 55:
            notes.append("Macro signal is balanced; avoid relying on macro alone.")

        return " ".join(notes)

    def _snapshot_from_dict(
        self,
        row: Dict[str, Any],
    ) -> ForexMacroSnapshot:
        asof_raw = row.get("asof")
        if isinstance(asof_raw, datetime):
            asof = asof_raw
        else:
            try:
                asof = datetime.fromisoformat(str(asof_raw))
            except Exception:
                asof = _utc_now()

        if asof.tzinfo is None:
            asof = asof.replace(tzinfo=timezone.utc)

        return ForexMacroSnapshot(
            macro_id=row.get("macro_id") or str(uuid.uuid4()),
            tenant_id=row.get("tenant_id"),
            user_id=row.get("user_id"),
            portfolio_id=row.get("portfolio_id"),
            pair=row.get("pair"),
            base_currency=row.get("base_currency"),
            quote_currency=row.get("quote_currency"),
            base_central_bank=row.get("base_central_bank"),
            quote_central_bank=row.get("quote_central_bank"),
            base_policy_rate=_safe_float(row.get("base_policy_rate")),
            quote_policy_rate=_safe_float(row.get("quote_policy_rate")),
            rate_differential=_safe_float(row.get("rate_differential")),
            base_inflation=_safe_float(row.get("base_inflation")),
            quote_inflation=_safe_float(row.get("quote_inflation")),
            inflation_differential=_safe_float(row.get("inflation_differential")),
            base_growth_score=_safe_float(row.get("base_growth_score")),
            quote_growth_score=_safe_float(row.get("quote_growth_score")),
            growth_differential=_safe_float(row.get("growth_differential")),
            usd_strength_score=_safe_float(row.get("usd_strength_score")),
            risk_regime_score=_safe_float(row.get("risk_regime_score")),
            risk_on_score=_safe_float(row.get("risk_on_score")),
            risk_off_score=_safe_float(row.get("risk_off_score")),
            commodity_signal=_safe_float(row.get("commodity_signal")),
            yield_signal=_safe_float(row.get("yield_signal")),
            central_bank_bias=row.get("central_bank_bias"),
            macro_direction=row.get("macro_direction"),
            macro_recommendation=row.get("macro_recommendation"),
            macro_score=_safe_float(row.get("macro_score")),
            confidence_score=_safe_float(row.get("confidence_score")),
            notes=row.get("notes", ""),
            asof=asof,
            raw=row.get("raw"),
        )

    def _row_to_snapshot_dict(
        self,
        row: Any,
    ) -> Dict[str, Any]:
        return {
            "macro_id": _row_get(row, "macro_id"),
            "tenant_id": _row_get(row, "tenant_id"),
            "user_id": _row_get(row, "user_id"),
            "portfolio_id": _row_get(row, "portfolio_id"),
            "pair": _row_get(row, "pair"),
            "base_currency": _row_get(row, "base_currency"),
            "quote_currency": _row_get(row, "quote_currency"),
            "base_central_bank": _row_get(row, "base_central_bank"),
            "quote_central_bank": _row_get(row, "quote_central_bank"),
            "base_policy_rate": _row_get(row, "base_policy_rate"),
            "quote_policy_rate": _row_get(row, "quote_policy_rate"),
            "rate_differential": _row_get(row, "rate_differential"),
            "base_inflation": _row_get(row, "base_inflation"),
            "quote_inflation": _row_get(row, "quote_inflation"),
            "inflation_differential": _row_get(row, "inflation_differential"),
            "base_growth_score": _row_get(row, "base_growth_score"),
            "quote_growth_score": _row_get(row, "quote_growth_score"),
            "growth_differential": _row_get(row, "growth_differential"),
            "usd_strength_score": _row_get(row, "usd_strength_score"),
            "risk_regime_score": _row_get(row, "risk_regime_score"),
            "risk_on_score": _row_get(row, "risk_on_score"),
            "risk_off_score": _row_get(row, "risk_off_score"),
            "commodity_signal": _row_get(row, "commodity_signal"),
            "yield_signal": _row_get(row, "yield_signal"),
            "central_bank_bias": _row_get(row, "central_bank_bias"),
            "macro_direction": _row_get(row, "macro_direction"),
            "macro_recommendation": _row_get(row, "macro_recommendation"),
            "macro_score": _row_get(row, "macro_score"),
            "confidence_score": _row_get(row, "confidence_score"),
            "notes": _row_get(row, "notes"),
            "asof": str(_row_get(row, "asof", "")),
            "raw": _row_get(row, "raw_payload"),
        }


def get_forex_macro_engine(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    forex_service: Optional[ForexService] = None,
) -> ForexMacroEngine:
    return ForexMacroEngine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
        forex_service=forex_service,
    )


def analyze_forex_macro(
    pair: str,
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    save: bool = True,
    macro_overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    engine = get_forex_macro_engine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )
    return engine.analyze_pair(
        pair,
        save=save,
        macro_overrides=macro_overrides,
    ).to_dict()


def run_forex_macro_scan(
    pairs: Optional[List[str]] = None,
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    save: bool = True,
    macro_overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    engine = get_forex_macro_engine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )
    return engine.scan_pairs(
        pairs=pairs,
        save=save,
        macro_overrides=macro_overrides,
    ).to_dict()