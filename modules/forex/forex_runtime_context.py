"""
modules/forex/forex_runtime_context.py

Sprint 27 Runtime Context Debug Build.
Builds one shared Forex runtime snapshot per dashboard render.

Primary goals:
- Exactly one Alpha execution per runtime build.
- No downstream engine should trigger another Alpha execution if runtime.alpha is missing.
- Extremely verbose start/end diagnostics for every runtime stage.
- Preserve existing public API: build_forex_runtime_context(...).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import threading
import time
import traceback
import uuid
from modules.forex.forex_ai import DEFAULT_FOREX_AI_PAIRS
try:
    from modules.forex.forex_portfolio_cache import get_forex_portfolio_cache
except Exception:
    get_forex_portfolio_cache = None

_RUNTIME_BUILD_COUNT = 0


# =============================================================================
# Helpers
# =============================================================================


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _component_state(context: "ForexRuntimeContext") -> Dict[str, bool]:
    return {
        "provider_health": context.provider_health is not None,
        "alpha": context.alpha is not None,
        "quotes": context.quotes is not None,
        "currency_strength": context.currency_strength is not None,
        "sentiment": context.sentiment is not None,
        "macro": context.macro is not None,
        "portfolio": context.portfolio is not None,
        "carry": context.carry is not None,
        "central_banks": context.central_banks is not None,
        "execution": context.execution is not None,
        "institutional": context.institutional is not None,

    }


def _brief(value: Any) -> Dict[str, Any]:
    """Small printable summary to avoid dumping huge payloads."""
    if value is None:
        return {"type": "NoneType", "is_none": True}

    out: Dict[str, Any] = {
        "type": type(value).__name__,
        "is_none": False,
        "id": id(value),
    }

    if isinstance(value, dict):
        out["keys"] = list(value.keys())[:20]
        if isinstance(value.get("signals"), list):
            out["signals"] = len(value.get("signals", []))
        if isinstance(value.get("top_opportunities"), list):
            out["top_opportunities"] = len(value.get("top_opportunities", []))
        if isinstance(value.get("currency_strength"), dict):
            out["has_currency_strength"] = True
        if isinstance(value.get("strength_scan"), dict):
            out["has_strength_scan"] = True
        if value.get("status") is not None:
            out["status"] = value.get("status")
        if value.get("error") is not None:
            out["error"] = str(value.get("error"))[:300]

    elif isinstance(value, list):
        out["len"] = len(value)

    return out


def _debug(runtime_id: str, message: str, **kwargs: Any) -> None:
    print("=" * 80)
    print(f"FOREX RUNTIME DEBUG | {runtime_id} | {message}")
    for key, value in kwargs.items():
        print(f"{key}: {value}")
    print("=" * 80)


def _stage_start(runtime_id: str, name: str, context: "ForexRuntimeContext") -> float:
    start = time.perf_counter()
    _debug(
        runtime_id,
        f"START {name}",
        runtime_object_id=id(context),
        alpha=_brief(context.alpha),
        components=_component_state(context),
    )
    context.metadata[f"{name.lower()}_started_at"] = _utc_now_iso()
    return start


def _stage_end(
    runtime_id: str,
    name: str,
    context: "ForexRuntimeContext",
    start: float,
    payload: Any = None,
) -> None:
    elapsed = _ms(start)
    context.metadata[f"{name.lower()}_ms"] = elapsed
    context.metadata[f"{name.lower()}_ended_at"] = _utc_now_iso()
    _debug(
        runtime_id,
        f"END {name}",
        elapsed_ms=elapsed,
        runtime_object_id=id(context),
        alpha=_brief(context.alpha),
        payload=_brief(payload),
        components=_component_state(context),
    )


def _stage_error(
    runtime_id: str,
    name: str,
    context: "ForexRuntimeContext",
    start: float,
    exc: Exception,
) -> None:
    elapsed = _ms(start)
    message = f"{type(exc).__name__}: {exc}"
    context.metadata[f"{name.lower()}_ms"] = elapsed
    context.metadata[f"{name.lower()}_failed_at"] = _utc_now_iso()
    context.diagnostics[name.lower()] = message
    context.diagnostics[f"{name.lower()}_traceback"] = traceback.format_exc()
    _debug(
        runtime_id,
        f"ERROR {name}",
        elapsed_ms=elapsed,
        error=message,
        traceback=traceback.format_exc(),
        runtime_object_id=id(context),
        alpha=_brief(context.alpha),
        components=_component_state(context),
    )


# =============================================================================
# Data Model
# =============================================================================


@dataclass
class ForexRuntimeContext:
    generated_at: str = field(default_factory=_utc_now_iso)
    force_refresh: bool = False
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    portfolio_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Runtime Data Fabric (Sprint 28)
    # ------------------------------------------------------------------

    # Shared quote cache (single download per runtime)
    quotes: Optional[Dict[str, Any]] = None

    # Metadata describing the shared quote cache
    quote_metadata: Optional[Dict[str, Any]] = None

    # Provider usage statistics
    quote_provider_summary: Optional[Dict[str, Any]] = None

    # Quote download timing
    quote_download_ms: float = 0.0

    # Shared analysis objects
    currency_strength: Optional[Dict[str, Any]] = None
    alpha: Optional[Dict[str, Any]] = None
    sentiment: Optional[Dict[str, Any]] = None
    macro: Optional[Dict[str, Any]] = None
    provider_health: Optional[Dict[str, Any]] = None
    portfolio: Optional[Dict[str, Any]] = None
    carry: Optional[Dict[str, Any]] = None
    central_banks: Optional[Dict[str, Any]] = None
    execution: Optional[Dict[str, Any]] = None
    institutional: Optional[Dict[str, Any]] = None

    metadata: Dict[str, Any] = field(default_factory=dict)
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    #
    # Sprint 29
    # Runtime Provider Telemetry
    #
    failed_providers: set = field(default_factory=set)

    provider_latency: Dict[str, float] = field(default_factory=dict)

    provider_usage: Dict[str, int] = field(default_factory=dict)

    last_provider: Optional[str] = None

    last_latency_ms: Optional[float] = None
    runtime_id: str | None = None

    tenant_id: str | None = None

    user_id: str | None = None

    portfolio_id: str | None = None

    session_id: str | None = None

    started_at: datetime | None = None

    def summary(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "force_refresh": self.force_refresh,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "portfolio_id": self.portfolio_id,
            "components": _component_state(self),
            "metadata": dict(self.metadata),
            "diagnostics": dict(self.diagnostics),
        }


# =============================================================================
# Derived fallbacks that DO NOT execute Alpha again
# =============================================================================


def _derive_sentiment_from_alpha(alpha: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(alpha, dict):
        return {
            "status": "DERIVED",
            "overall_sentiment": "NEUTRAL",
            "pair_sentiment": [],
            "top_sentiment_trades": [],
            "source": "runtime_fallback_no_alpha",
        }

    signals = alpha.get("signals", [])
    if not isinstance(signals, list):
        signals = []

    buys = 0
    sells = 0
    rows = []

    for signal in signals:
        if not isinstance(signal, dict):
            continue

        direction = str(
            signal.get("direction")
            or signal.get("recommendation")
            or ""
        ).upper()

        if any(x in direction for x in ("BUY", "LONG", "BULL")):
            buys += 1
            sentiment = "BULLISH"
        elif any(x in direction for x in ("SELL", "SHORT", "BEAR")):
            sells += 1
            sentiment = "BEARISH"
        else:
            sentiment = "NEUTRAL"

        rows.append({
            "pair": signal.get("pair") or signal.get("symbol"),
            "market_sentiment": sentiment,
            "sentiment_score": signal.get("alpha_score"),
            "confidence_score": signal.get("confidence_score"),
            "direction": direction or "NEUTRAL",
            "recommendation": signal.get("recommendation"),
            "source": "runtime_alpha_derived",
        })

    if buys > sells:
        overall = "BULLISH"
    elif sells > buys:
        overall = "BEARISH"
    else:
        overall = "NEUTRAL"

    return {
        "status": "DERIVED",
        "generated_at": _utc_now_iso(),
        "overall_sentiment": overall,
        "bullish_signals": buys,
        "bearish_signals": sells,
        "pair_sentiment": rows,
        "top_sentiment_trades": rows[:10],
        "source": "runtime_alpha_derived",
    }


def _derive_institutional_from_alpha(alpha: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(alpha, dict):
        return {
            "status": "DERIVED",
            "institutional_flow": [],
            "top_institutional_trades": [],
            "source": "runtime_fallback_no_alpha",
        }

    signals = alpha.get("signals", [])
    if not isinstance(signals, list):
        signals = []

    flows = []

    for signal in signals[:10]:
        if not isinstance(signal, dict):
            continue

        try:
            score = float(
                signal.get("alpha_score")
                or signal.get("conviction_score")
                or 0
            )
        except Exception:
            score = 0.0

        direction = str(
            signal.get("direction")
            or signal.get("recommendation")
            or "NEUTRAL"
        ).upper()

        if score >= 80:
            bias = (
                "STRONG_INSTITUTIONAL_ACCUMULATION"
                if any(x in direction for x in ("BUY", "LONG", "BULL"))
                else "STRONG_INSTITUTIONAL_DISTRIBUTION"
            )
        elif score >= 65:
            bias = (
                "ACCUMULATION"
                if any(x in direction for x in ("BUY", "LONG", "BULL"))
                else "DISTRIBUTION"
            )
        else:
            bias = "NEUTRAL"

        flows.append({
            "pair": signal.get("pair") or signal.get("symbol"),
            "institutional_bias": bias,
            "smart_money_score": round(score, 2),
            "confidence": signal.get("confidence_score"),
            "direction": direction,
            "recommendation": signal.get("recommendation"),
            "source": "runtime_alpha_derived",
        })

    return {
        "status": "DERIVED",
        "generated_at": _utc_now_iso(),
        "institutional_flow": flows,
        "top_institutional_trades": flows[:10],
        "source": "runtime_alpha_derived",
    }


# =============================================================================
# Runtime Builder
# =============================================================================


class ForexRuntimeContextBuilder:
    def __init__(self, db: Any = None):
        self.db = db
        self._lock = threading.RLock()

    def build(
        self,
        *,
        tenant_id=None,
        user_id=None,
        portfolio_id=None,
        force_refresh=False,
    ) -> ForexRuntimeContext:
        global _RUNTIME_BUILD_COUNT

        runtime_id = uuid.uuid4().hex[:8]
        overall_start = time.perf_counter()

        with self._lock:
            _RUNTIME_BUILD_COUNT += 1
            build_number = _RUNTIME_BUILD_COUNT

            context = ForexRuntimeContext(
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=portfolio_id,
                force_refresh=force_refresh,
            )
            context.metadata["runtime_id"] = runtime_id
            context.metadata["runtime_build_number"] = build_number
            context.metadata["runtime_object_id"] = id(context)
            context.metadata["build_started_at"] = _utc_now_iso()
            context.provider_failures = set()
            _debug(
                runtime_id,
                "BUILD START",
                build_number=build_number,
                runtime_object_id=id(context),
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=portfolio_id,
                force_refresh=force_refresh,
            )
            pairs = DEFAULT_FOREX_AI_PAIRS
            # -----------------------------------------------------------------
            # Provider Health
            # -----------------------------------------------------------------
            start = _stage_start(runtime_id, "PROVIDER_HEALTH", context)
            try:
                from modules.forex.forex_provider_health import get_forex_provider_health

                provider = get_forex_provider_health()
                if hasattr(provider, "summary"):
                    context.provider_health = provider.summary()
                else:
                    context.provider_health = {"status": "UNAVAILABLE"}
                _stage_end(runtime_id, "PROVIDER_HEALTH", context, start, context.provider_health)
            except Exception as exc:
                _stage_error(runtime_id, "PROVIDER_HEALTH", context, start, exc)



            # -----------------------------------------------------------------
            # Quotes
            # -----------------------------------------------------------------
            start = _stage_start(runtime_id, "QUOTES", context)

            try:
                from modules.forex.forex_price_service import (
                    get_forex_price_service,
                )

                price_service = get_forex_price_service()

                quote_start = time.perf_counter()

                context.quotes = price_service.load_runtime_quotes(
                    pairs=pairs,
                    force_refresh=force_refresh,
                )

                context.quote_download_ms = _ms(quote_start)

                context.quote_metadata = {
                    "generated_at": _utc_now_iso(),
                    "pair_count": (
                        len(context.quotes)
                        if isinstance(context.quotes, dict)
                        else 0
                    ),
                    "download_ms": context.quote_download_ms,
                    "source": "runtime",
                }

                _stage_end(
                    runtime_id,
                    "QUOTES",
                    context,
                    start,
                    context.quote_metadata,
                )

            except Exception as exc:
                _stage_error(
                    runtime_id,
                    "QUOTES",
                    context,
                    start,
                    exc,
                )

            # -----------------------------------------------------------------
            # Alpha: THE ONLY intended Alpha execution inside a runtime build.
            # -----------------------------------------------------------------
            start = _stage_start(runtime_id, "ALPHA", context)
            try:
                from modules.forex.forex_alpha_model import get_forex_alpha_model

                alpha_engine = get_forex_alpha_model()
                alpha_payload: Any = None

                if hasattr(alpha_engine, "run_alpha_model"):
                    _debug(
                        runtime_id,
                        "ALPHA CALL run_alpha_model",
                        runtime_object_id=id(context),
                        force_refresh=force_refresh,
                    )
                    runtime_pairs = (
                        list(context.quotes.keys())
                        if isinstance(context.quotes, dict)
                        else None
                    )
                    _debug(
                        runtime_id,
                        "ALPHA INPUT",
                        quote_count=len(context.quotes)
                        if isinstance(context.quotes, dict)
                        else 0,
                        pair_count=len(runtime_pairs)
                        if runtime_pairs
                        else 0,
                    )
                    alpha_payload = alpha_engine.run_alpha_model(
                        pairs=runtime_pairs,
                        quotes=context.quotes,
                        force_refresh=force_refresh,
                    )
                elif hasattr(alpha_engine, "command_center_payload"):
                    _debug(
                        runtime_id,
                        "ALPHA CALL command_center_payload",
                        runtime_object_id=id(context),
                        force_refresh=force_refresh,
                    )
                    alpha_payload = alpha_engine.command_center_payload(
                        force_refresh=force_refresh,
                    )
                else:
                    alpha_payload = {
                        "status": "UNAVAILABLE",
                        "signals": [],
                        "error": "Alpha engine has no run_alpha_model or command_center_payload method.",
                    }

                if isinstance(alpha_payload, dict):
                    context.alpha = alpha_payload
                else:
                    context.alpha = {
                        "status": "INVALID_ALPHA_PAYLOAD",
                        "signals": [],
                        "payload_type": type(alpha_payload).__name__,
                    }
                    context.diagnostics["alpha_payload_type"] = type(alpha_payload).__name__

                # Optional: capture quotes if Alpha starts returning them in Sprint 27/28.
                if isinstance(context.alpha, dict):
                    #quotes = context.alpha.get("quotes") or context.alpha.get("quote_cache")
                    #if isinstance(quotes, dict):
                        #context.quotes = quotes

                    _stage_end(runtime_id, "ALPHA", context, start, context.alpha)

            except Exception as exc:
                # Important: do NOT allow downstream engines to execute Alpha again.
                context.alpha = None
                _stage_error(runtime_id, "ALPHA", context, start, exc)

            # -----------------------------------------------------------------
            # Currency Strength: reuse Alpha payload. Do not re-download if Alpha
            # provided currency strength.
            # -----------------------------------------------------------------
            start = _stage_start(runtime_id, "CURRENCY_STRENGTH", context)
            try:
                if isinstance(context.alpha, dict):
                    if isinstance(context.alpha.get("currency_strength"), dict):
                        context.currency_strength = context.alpha["currency_strength"]
                        context.metadata["currency_strength_source"] = "alpha.currency_strength"
                    elif isinstance(context.alpha.get("strength_scan"), dict):
                        context.currency_strength = context.alpha["strength_scan"]
                        context.metadata["currency_strength_source"] = "alpha.strength_scan"

                if context.currency_strength is None:
                    # Only fallback if Alpha completed but did not provide strength.
                    # This is not an Alpha execution, but may still touch quotes.
                    from modules.forex.forex_currency_strength_engine import (
                        get_forex_currency_strength_engine,
                    )

                    strength = get_forex_currency_strength_engine()
                    if hasattr(strength, "scan_currencies"):
                        context.currency_strength = strength.scan_currencies(
                            force_refresh=force_refresh,
                        )
                        context.metadata["currency_strength_source"] = "local.scan_currencies"
                    elif hasattr(strength, "command_center_payload"):
                        context.currency_strength = strength.command_center_payload(
                            force_refresh=force_refresh,
                        )
                        context.metadata["currency_strength_source"] = "local.command_center_payload"

                _stage_end(runtime_id, "CURRENCY_STRENGTH", context, start, context.currency_strength)
            except Exception as exc:
                _stage_error(runtime_id, "CURRENCY_STRENGTH", context, start, exc)

            # -----------------------------------------------------------------
            # Sentiment: IMPORTANT. If Alpha failed/missing, derive fallback.
            # Do NOT call sentiment.analyze(), because that engine may fallback
            # to self.alpha.run_alpha_model() and duplicate quotes.
            # -----------------------------------------------------------------
            start = _stage_start(runtime_id, "SENTIMENT", context)
            try:
                if isinstance(context.alpha, dict):
                    from modules.forex.forex_sentiment_engine import get_forex_sentiment_engine

                    sentiment_engine = get_forex_sentiment_engine()
                    try:
                        context.sentiment = sentiment_engine.analyze(
                            runtime=context,
                            force_refresh=force_refresh,
                        )
                        context.metadata["sentiment_source"] = "engine.runtime"
                    except TypeError:
                        context.sentiment = _derive_sentiment_from_alpha(context.alpha)
                        context.metadata["sentiment_source"] = "derived_typeerror"
                else:
                    context.sentiment = _derive_sentiment_from_alpha(context.alpha)
                    context.metadata["sentiment_source"] = "derived_no_alpha"

                _stage_end(runtime_id, "SENTIMENT", context, start, context.sentiment)
            except Exception as exc:
                context.sentiment = _derive_sentiment_from_alpha(context.alpha)
                context.metadata["sentiment_source"] = "derived_exception"
                _stage_error(runtime_id, "SENTIMENT", context, start, exc)

            # -----------------------------------------------------------------
            # Macro
            # -----------------------------------------------------------------
            start = _stage_start(runtime_id, "MACRO", context)
            try:
                from modules.forex.forex_macro_regime_engine import get_forex_macro_regime_engine

                macro = get_forex_macro_regime_engine()
                if hasattr(macro, "analyze"):
                    context.macro = macro.analyze(
                        runtime=context,
                        force_refresh=force_refresh,
                    )
                _stage_end(runtime_id, "MACRO", context, start, context.macro)
            except Exception as exc:
                _stage_error(runtime_id, "MACRO", context, start, exc)

            # -----------------------------------------------------------------
            # Portfolio
            # -----------------------------------------------------------------
            start = _stage_start(runtime_id, "PORTFOLIO", context)
            try:
                cached = None
                if get_forex_portfolio_cache is not None:
                    cache = get_forex_portfolio_cache()
                    cached = cache.get_summary(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        portfolio_id=portfolio_id,
                    )

                if cached is not None and not force_refresh:
                    context.portfolio = cached
                    context.metadata["portfolio_source"] = "cache"
                else:
                    from modules.forex.forex_portfolio_manager import get_forex_portfolio_manager

                    try:
                        portfolio = get_forex_portfolio_manager(
                            db=self.db,
                            tenant_id=tenant_id,
                            user_id=user_id,
                            portfolio_id=portfolio_id,
                        )
                    except TypeError:
                        portfolio = get_forex_portfolio_manager(db=self.db)

                    if hasattr(portfolio, "portfolio_summary"):
                        context.portfolio = portfolio.portfolio_summary(
                            tenant_id=tenant_id,
                            user_id=user_id,
                            portfolio_id=portfolio_id,
                            force_refresh=force_refresh,
                        )
                        context.metadata["portfolio_source"] = "manager"

                _stage_end(runtime_id, "PORTFOLIO", context, start, context.portfolio)
            except Exception as exc:
                _stage_error(runtime_id, "PORTFOLIO", context, start, exc)

            # -----------------------------------------------------------------
            # Carry
            # -----------------------------------------------------------------
            start = _stage_start(runtime_id, "CARRY", context)
            try:
                from modules.forex.forex_carry_trade_engine import get_forex_carry_trade_engine

                carry = get_forex_carry_trade_engine()
                if hasattr(carry, "analyze"):
                    context.carry = carry.analyze(
                        runtime=context,
                        force_refresh=force_refresh,
                    )
                _stage_end(runtime_id, "CARRY", context, start, context.carry)
            except TypeError:
                try:
                    context.carry = carry.analyze()
                    _stage_end(runtime_id, "CARRY", context, start, context.carry)
                except Exception as exc:
                    _stage_error(runtime_id, "CARRY", context, start, exc)
            except Exception as exc:
                _stage_error(runtime_id, "CARRY", context, start, exc)

            # -----------------------------------------------------------------
            # Central Banks
            # -----------------------------------------------------------------
            start = _stage_start(runtime_id, "CENTRAL_BANKS", context)
            try:
                from modules.forex.forex_central_bank_engine import get_forex_central_bank_engine

                cb = get_forex_central_bank_engine()
                if hasattr(cb, "analyze"):
                    context.central_banks = cb.analyze()
                _stage_end(runtime_id, "CENTRAL_BANKS", context, start, context.central_banks)
            except Exception as exc:
                _stage_error(runtime_id, "CENTRAL_BANKS", context, start, exc)

            # -----------------------------------------------------------------
            # Institutional: same rule as Sentiment. If Alpha failed/missing,
            # derive fallback and do not call scanner.scan(), because scanner
            # can fallback to self.alpha.run_alpha_model().
            # -----------------------------------------------------------------
            start = _stage_start(runtime_id, "INSTITUTIONAL", context)
            try:
                if isinstance(context.alpha, dict):
                    from modules.forex.forex_institutional_scanner import (
                        get_forex_institutional_scanner,
                    )

                    scanner = get_forex_institutional_scanner()
                    try:
                        context.institutional = scanner.scan(
                            runtime=context,
                            force_refresh=force_refresh,
                        )
                        context.metadata["institutional_source"] = "engine.runtime"
                    except TypeError:
                        context.institutional = _derive_institutional_from_alpha(context.alpha)
                        context.metadata["institutional_source"] = "derived_typeerror"
                else:
                    context.institutional = _derive_institutional_from_alpha(context.alpha)
                    context.metadata["institutional_source"] = "derived_no_alpha"

                _stage_end(runtime_id, "INSTITUTIONAL", context, start, context.institutional)
            except Exception as exc:
                context.institutional = _derive_institutional_from_alpha(context.alpha)
                context.metadata["institutional_source"] = "derived_exception"
                _stage_error(runtime_id, "INSTITUTIONAL", context, start, exc)

            # -----------------------------------------------------------------
            # Finish
            # -----------------------------------------------------------------
            context.metadata["runtime_total_ms"] = _ms(overall_start)
            context.metadata["build_finished_at"] = _utc_now_iso()

            _debug(
                runtime_id,
                "BUILD FINISHED",
                total_ms=context.metadata["runtime_total_ms"],
                summary=context.summary(),
            )
            #
            # Sprint 29
            # Runtime Provider Summary
            #
            _debug(
                runtime_id,
                "PROVIDER RUNTIME SUMMARY",
                provider_usage=getattr(
                    context,
                    "provider_usage",
                    {},
                ),
                failed_providers=sorted(
                    getattr(
                        context,
                        "failed_providers",
                        set(),
                    )
                ),
                provider_latency=getattr(
                    context,
                    "provider_latency",
                    {},
                ),
            )
            # ============================================================================
            # Sprint 30 Phase 1
            # Runtime Telemetry
            # ============================================================================

            try:
                from modules.forex.forex_runtime_telemetry_engine import (
                    get_runtime_telemetry_engine,
                )

                get_runtime_telemetry_engine().record_runtime(
                    context,
                )

            except Exception as exc:

                print("=" * 80)
                print("FOREX RUNTIME TELEMETRY FAILED")
                print(repr(exc))
                print("=" * 80)

            return context



_BUILDER: Optional[ForexRuntimeContextBuilder] = None


def get_forex_runtime_builder(db: Any = None) -> ForexRuntimeContextBuilder:
    global _BUILDER

    if _BUILDER is None or (db is not None and getattr(_BUILDER, "db", None) is None):
        _BUILDER = ForexRuntimeContextBuilder(db=db)

    return _BUILDER


def build_forex_runtime_context(
    *,
    tenant_id=None,
    user_id=None,
    portfolio_id=None,
    force_refresh=False,
    db=None,
) -> ForexRuntimeContext:
    return get_forex_runtime_builder(db=db).build(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        force_refresh=force_refresh,
    )
