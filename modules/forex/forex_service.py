"""
modules/forex/forex_service.py

Cycle-safe service facade for the Forex subsystem.

This upgraded service provides the stable compatibility layer expected by:
- forex_ai.py
- forex_portfolio_engine.py
- forex_terminal_dashboard.py
- forex execution / validation / AI workspaces

Important:
- This file intentionally avoids importing forex_application at module import time.
- Provider / engine imports are kept inside methods to avoid circular imports.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from modules.forex.forex_quant_research_db import (
    initialize_forex_quant_research_schema,
)
from modules.forex.forex_factor_models_db import (
    initialize_forex_factor_models_schema,
)
# ---------------------------------------------------------------------
# Common helpers
# ---------------------------------------------------------------------

try:
    from modules.forex.forex_common import (
        normalize_pair as _common_normalize_pair,
        split_pair as _common_split_pair,
    )
except Exception:
    _common_normalize_pair = None
    _common_split_pair = None


def normalize_pair(pair: Any) -> str:
    """Normalize EURUSD / eur-usd / eur_usd into EUR/USD."""
    if _common_normalize_pair is not None:
        try:
            return _common_normalize_pair(pair)
        except Exception:
            pass

    value = str(pair or "").upper().strip()
    value = value.replace("-", "").replace("_", "").replace("/", "").replace(" ", "")
    if len(value) == 6:
        return f"{value[:3]}/{value[3:]}"
    return value or "EUR/USD"


def split_pair(pair: Any) -> Tuple[str, str]:
    """Return base and quote currency from a normalized FX pair."""
    if _common_split_pair is not None:
        try:
            return _common_split_pair(pair)
        except Exception:
            pass

    value = normalize_pair(pair).replace("/", "")
    if len(value) >= 6:
        return value[:3], value[3:6]
    return "EUR", "USD"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str):
            value = value.replace(",", "").replace("%", "").replace("$", "").strip()
            if value in {"", "-", "—", "None", "nan"}:
                return default
        return float(value)
    except Exception:
        return default


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------
# Supported pairs / metadata
# ---------------------------------------------------------------------

# ---------------------------------------------------------------------
# Pair metadata (Institutional API)
# ---------------------------------------------------------------------

MAJOR_PAIR_METADATA: Dict[str, Dict[str, float]] = {
    "EUR/USD": {"pip_size": 0.0001, "pip_value_per_standard_lot": 10.0},
    "GBP/USD": {"pip_size": 0.0001, "pip_value_per_standard_lot": 10.0},
    "AUD/USD": {"pip_size": 0.0001, "pip_value_per_standard_lot": 10.0},
    "NZD/USD": {"pip_size": 0.0001, "pip_value_per_standard_lot": 10.0},
    "USD/CAD": {"pip_size": 0.0001, "pip_value_per_standard_lot": 10.0},
    "USD/CHF": {"pip_size": 0.0001, "pip_value_per_standard_lot": 10.0},
    "USD/JPY": {"pip_size": 0.01, "pip_value_per_standard_lot": 9.0},
}

CROSS_PAIR_METADATA: Dict[str, Dict[str, float]] = {
    "EUR/GBP": {"pip_size": 0.0001, "pip_value_per_standard_lot": 10.0},
    "EUR/JPY": {"pip_size": 0.01, "pip_value_per_standard_lot": 9.0},
    "GBP/JPY": {"pip_size": 0.01, "pip_value_per_standard_lot": 9.0},
    "AUD/JPY": {"pip_size": 0.01, "pip_value_per_standard_lot": 9.0},
    "EUR/CHF": {"pip_size": 0.0001, "pip_value_per_standard_lot": 10.0},
    "GBP/CHF": {"pip_size": 0.0001, "pip_value_per_standard_lot": 10.0},
    "CAD/JPY": {"pip_size": 0.01, "pip_value_per_standard_lot": 9.0},
    "CHF/JPY": {"pip_size": 0.01, "pip_value_per_standard_lot": 9.0},
    "EUR/AUD": {"pip_size": 0.0001, "pip_value_per_standard_lot": 10.0},
    "EUR/CAD": {"pip_size": 0.0001, "pip_value_per_standard_lot": 10.0},
    "AUD/CAD": {"pip_size": 0.0001, "pip_value_per_standard_lot": 10.0},
    "AUD/NZD": {"pip_size": 0.0001, "pip_value_per_standard_lot": 10.0},
}

# ---------------------------------------------------------------------
# Legacy compatibility (all existing Forex modules expect LISTS)
# ---------------------------------------------------------------------

MAJOR_PAIRS = list(MAJOR_PAIR_METADATA.keys())

CROSS_PAIRS = list(CROSS_PAIR_METADATA.keys())

SUPPORTED_PAIRS = MAJOR_PAIRS + CROSS_PAIRS

PAIR_METADATA = {
    **MAJOR_PAIR_METADATA,
    **CROSS_PAIR_METADATA,
}

SUPPORTED_CURRENCIES: List[str] = sorted({
    currency
    for pair in SUPPORTED_PAIRS
    for currency in split_pair(pair)
})

DEFAULT_PROVIDER = "ForexService"


# ---------------------------------------------------------------------
# Quote model
# ---------------------------------------------------------------------

@dataclass
class ForexQuote:
    pair: str
    bid: float = 0.0
    ask: float = 0.0
    mid: float = 0.0
    spread: float = 0.0
    timestamp: Optional[datetime] = None
    provider: str = DEFAULT_PROVIDER
    volume: float = 0.0
    source: str = "service"

    @property
    def base(self) -> str:
        return split_pair(self.pair)[0]

    @property
    def quote(self) -> str:
        return split_pair(self.pair)[1]

    @property
    def price(self) -> float:
        if self.mid and self.mid > 0:
            return float(self.mid)
        if self.bid and self.ask and self.bid > 0 and self.ask > 0:
            return (float(self.bid) + float(self.ask)) / 2.0
        if self.bid and self.bid > 0:
            return float(self.bid)
        if self.ask and self.ask > 0:
            return float(self.ask)
        return 0.0

    @property
    def asof(self) -> datetime:
        return self.timestamp or _utc_now()

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["pair"] = normalize_pair(self.pair)
        data["base"] = self.base
        data["quote"] = self.quote
        data["price"] = self.price
        data["asof"] = self.asof.isoformat()
        data["timestamp"] = self.asof.isoformat()
        return data


# ---------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------

class ForexService:
    def __init__(
            self,
            db=None,
            *,
            tenant_id=None,
            user_id=None,
            portfolio_id=None,
    ):
        self.db = db
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.portfolio_id = portfolio_id

    # -------------------------------
    # Lifecycle
    # -------------------------------

    def initialize(self):

        self.initialize_database()

        return {
            "status": "READY",
            "component": "ForexService",
        }

    def shutdown(self) -> Dict[str, Any]:
        return {"status": "STOPPED", "component": "ForexService"}

    def diagnostics(self) -> Dict[str, Any]:
        return {
            "status": "READY",
            "component": "ForexService",
            "timestamp": _utc_now().isoformat(),
            "pairs_supported": len(SUPPORTED_PAIRS),
            "currencies_supported": len(SUPPORTED_CURRENCIES),
            "db_attached": self.db is not None,
        }

    def render(self):
        try:
            from modules.forex.forex_workspace import render_forex_workspace
            return render_forex_workspace(
                db=self.db,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                portfolio_id=self.portfolio_id,
            )
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    # -------------------------------
    # Pair metadata
    # -------------------------------

    def supported_pairs(self) -> List[str]:
        return list(SUPPORTED_PAIRS)

    def supported_currencies(self) -> List[str]:
        return list(SUPPORTED_CURRENCIES)

    def pair_metadata(self, pair: Any) -> Dict[str, Any]:
        normalized = normalize_pair(pair)
        meta = dict(
            PAIR_METADATA.get(normalized)
            or {}
        )
        meta.setdefault("pip_size", 0.01 if normalized.endswith("/JPY") else 0.0001)
        meta.setdefault("pip_value_per_standard_lot", 9.0 if normalized.endswith("/JPY") else 10.0)
        meta["pair"] = normalized
        meta["base"], meta["quote"] = split_pair(normalized)
        return meta

    # -------------------------------
    # Quotes
    # -------------------------------

    def get_quote(self, pair: Any = "EUR/USD") -> ForexQuote:
        """
        Return a ForexQuote compatible with forex_ai.py.

        Provider chain:
        1. forex_quote_aggregator.quote()
        2. forex_provider_router / provider modules if available
        3. deterministic synthetic fallback
        """
        normalized = normalize_pair(pair)

        quote = self._quote_from_aggregator(normalized)
        if quote is not None:
            return quote

        quote = self._quote_from_router(normalized)
        if quote is not None:
            return quote

        return self._fallback_quote(normalized)

    def get_quotes(self, pairs: Optional[List[str]] = None) -> Dict[str, ForexQuote]:
        selected = pairs or SUPPORTED_PAIRS
        return {normalize_pair(pair): self.get_quote(pair) for pair in selected}

    def quote(self, pair: Any = "EUR/USD") -> Dict[str, Any]:
        return self.get_quote(pair).to_dict()

    def quotes(self, pairs: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        return {pair: quote.to_dict() for pair, quote in self.get_quotes(pairs).items()}

    def latest_price(self, pair: Any = "EUR/USD") -> float:
        return self.get_quote(pair).price

    def latest_price_map(self, pairs: Optional[List[str]] = None) -> Dict[str, float]:
        return {pair: quote.price for pair, quote in self.get_quotes(pairs).items()}

    def _quote_from_aggregator(self, pair: str) -> Optional[ForexQuote]:
        try:
            from modules.forex.forex_quote_aggregator import ForexQuoteAggregator
            aggregator = ForexQuoteAggregator(db=self.db)
            result = aggregator.quote(pair)
            return self._coerce_quote(result, pair, provider="Aggregator")
        except Exception:
            return None

    def _quote_from_router(self, pair: str) -> Optional[ForexQuote]:
        try:
            from modules.forex.providers.forex_provider_router import get_forex_provider_router
            router = get_forex_provider_router()
            if hasattr(router, "quote"):
                result = router.quote(pair)
                return self._coerce_quote(result, pair, provider="ProviderRouter")
            if hasattr(router, "get_quote"):
                result = router.get_quote(pair)
                return self._coerce_quote(result, pair, provider="ProviderRouter")
        except Exception:
            return None
        return None

    def _coerce_quote(self, result: Any, pair: str, provider: str = DEFAULT_PROVIDER) -> Optional[ForexQuote]:
        if result is None:
            return None

        if isinstance(result, ForexQuote):
            return result

        if hasattr(result, "to_dict"):
            try:
                result = result.to_dict()
            except Exception:
                pass

        if not isinstance(result, dict):
            return None

        status = str(result.get("status", "OK")).upper()
        if status in {"ERROR", "FAILED", "UNAVAILABLE"}:
            return None

        bid = _safe_float(result.get("bid"))
        ask = _safe_float(result.get("ask"))
        mid = _safe_float(
            result.get("mid")
            or result.get("price")
            or result.get("last")
            or result.get("rate")
            or result.get("close")
        )

        if mid <= 0 and bid > 0 and ask > 0:
            mid = (bid + ask) / 2.0

        if mid <= 0:
            return None

        if bid <= 0:
            bid = mid
        if ask <= 0:
            ask = mid

        spread = _safe_float(result.get("spread"), abs(ask - bid))

        timestamp = result.get("timestamp") or result.get("asof") or result.get("time")
        asof = self._parse_datetime(timestamp)

        return ForexQuote(
            pair=normalize_pair(result.get("pair") or result.get("symbol") or pair),
            bid=bid,
            ask=ask,
            mid=mid,
            spread=spread,
            timestamp=asof,
            provider=str(result.get("provider") or provider),
            volume=_safe_float(result.get("volume")),
            source=str(result.get("source") or provider),
        )

    def _fallback_quote(self, pair: str) -> ForexQuote:
        normalized = normalize_pair(pair)
        defaults = {
            "EUR/USD": 1.0800,
            "GBP/USD": 1.2700,
            "AUD/USD": 0.6600,
            "NZD/USD": 0.6100,
            "USD/CAD": 1.3700,
            "USD/CHF": 0.9000,
            "USD/JPY": 157.00,
            "EUR/GBP": 0.8500,
            "EUR/JPY": 169.50,
            "GBP/JPY": 199.00,
            "AUD/JPY": 103.50,
            "EUR/CHF": 0.9700,
            "GBP/CHF": 1.1400,
            "CAD/JPY": 114.50,
            "CHF/JPY": 174.00,
            "EUR/AUD": 1.6400,
            "EUR/CAD": 1.4800,
            "AUD/CAD": 0.9050,
            "AUD/NZD": 1.0800,
        }
        mid = defaults.get(normalized, 1.0000)
        pip = self.pair_metadata(normalized)["pip_size"]
        spread = pip * 1.2
        return ForexQuote(
            pair=normalized,
            bid=round(mid - spread / 2, 6),
            ask=round(mid + spread / 2, 6),
            mid=round(mid, 6),
            spread=round(spread, 6),
            timestamp=_utc_now(),
            provider="Fallback",
            volume=0.0,
            source="synthetic_fallback",
        )

    @staticmethod
    def _parse_datetime(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and value:
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except Exception:
                return _utc_now()
        return _utc_now()

    # -------------------------------
    # Engine facades
    # -------------------------------

    def refresh_market_data(self) -> Dict[str, Any]:
        try:
            from modules.forex.forex_refresh_engine import get_forex_refresh_engine
            engine = get_forex_refresh_engine()
            if hasattr(engine, "refresh"):
                return engine.refresh()
            if hasattr(engine, "run"):
                return engine.run()
            return {"status": "READY", "message": "Refresh engine loaded."}
        except Exception as exc:
            return {"status": "WARNING", "message": "Refresh engine unavailable.", "error": str(exc)}

    def get_command_center(self) -> Dict[str, Any]:
        try:
            from modules.forex.forex_command_center_engine import get_forex_command_center_engine
            engine = get_forex_command_center_engine()
            if hasattr(engine, "build"):
                return engine.build(
                    runtime=self.runtime,
                    force_refresh=False,
                )
            return {"status": "READY", "component": type(engine).__name__}
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    def get_alpha_recommendations(self) -> Dict[str, Any]:
        try:
            from modules.forex.forex_alpha_model import get_forex_alpha_model
            engine = get_forex_alpha_model()
            if hasattr(engine, "command_center_payload"):
                return engine.command_center_payload(force_refresh=False)
            if hasattr(engine, "run_alpha_model"):
                return engine.run_alpha_model(force_refresh=False)
            return {"status": "READY", "component": type(engine).__name__}
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    def get_currency_strength(self) -> Dict[str, Any]:
        try:
            from modules.forex.forex_currency_strength_engine import get_forex_currency_strength_engine
            engine = get_forex_currency_strength_engine()
            if hasattr(engine, "command_center_payload"):
                return engine.command_center_payload(force_refresh=False)
            if hasattr(engine, "analyze"):
                return engine.analyze(force_refresh=False)
            return {"status": "READY", "component": type(engine).__name__}
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    def get_macro_regime(self) -> Dict[str, Any]:
        try:
            from modules.forex.forex_macro_regime_engine import get_forex_macro_regime_engine
            engine = get_forex_macro_regime_engine()
            if hasattr(engine, "analyze"):
                return engine.analyze(force_refresh=False)
            return {"status": "READY", "component": type(engine).__name__}
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    def get_sentiment(self) -> Dict[str, Any]:
        try:
            from modules.forex.forex_sentiment_engine import get_forex_sentiment_engine
            engine = get_forex_sentiment_engine()
            if hasattr(engine, "analyze"):
                return engine.analyze(force_refresh=False)
            return {"status": "READY", "component": type(engine).__name__}
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    def snapshot(self) -> Dict[str, Any]:
        quotes = self.quotes(SUPPORTED_PAIRS[:8])
        return {
            "status": "READY",
            "generated_at": _utc_now().isoformat(),
            "quotes": quotes,
            "supported_pairs": SUPPORTED_PAIRS,
            "supported_currencies": SUPPORTED_CURRENCIES,
            "diagnostics": self.diagnostics(),
        }

    def initialize_database(self):

        if self.db is None:
            return

        initialize_forex_quant_research_schema(self.db)
        initialize_forex_factor_models_schema(self.db)

        from modules.forex.forex_history_repository import ensure_forex_price_history_tables

        ensure_forex_price_history_tables(self.db)


    def get_quant_research_engine(self):

        if not hasattr(self, "_quant_research_engine"):
            from modules.forex.forex_quant_research_engine import (
                ForexQuantResearchEngine,
            )

            self._quant_research_engine = ForexQuantResearchEngine(
                db=self.db,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                portfolio_id=self.portfolio_id,
            )

        return self._quant_research_engine

    def get_factor_models_engine(self):

        if not hasattr(self, "_factor_models_engine"):
            from modules.forex.forex_factor_models_engine import (
                ForexFactorModelsEngine,
            )

            self._factor_models_engine = ForexFactorModelsEngine(
                db=self.db,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                portfolio_id=self.portfolio_id,
            )

        return self._factor_models_engine

    def get_history_service(self):

        if not hasattr(self, "_history_service"):
            from modules.forex.forex_history_service import (
                ForexHistoryService,
            )

            self._history_service = ForexHistoryService(
                db=self.db,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                portfolio_id=self.portfolio_id,
            )

        return self._history_service

    def get_history_refresh_engine(self):
        from modules.forex.forex_history_refresh_engine import ForexHistoryRefreshEngine

        return ForexHistoryRefreshEngine(
            db=self.db,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,
            service=self.get_history_service(),
        )




_SERVICE: Optional[ForexService] = None


def get_forex_service(
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Optional[Any] = None,
) -> ForexService:

    global _SERVICE

    if (
        _SERVICE is None
        or _SERVICE.db is not db
        or _SERVICE.tenant_id != tenant_id
        or _SERVICE.user_id != user_id
        or _SERVICE.portfolio_id != portfolio_id
    ):

        _SERVICE = ForexService(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )

    return _SERVICE
