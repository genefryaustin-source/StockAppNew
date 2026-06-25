"""
modules/forex/providers/forex_provider_router.py

Central Forex quote router for StockApp.

Pattern intentionally mirrors the existing Options provider router:
- ordered providers
- in-memory TTL cache
- provider cooldowns
- failover
- normalized quote payload
- bulk quote helper
"""

from __future__ import annotations

import importlib
import math
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from threading import Lock
from typing import Any, Callable, Iterable, Optional


DEFAULT_CACHE_TTL_SECONDS = 60
RATE_LIMIT_COOLDOWN_SECONDS = 15 * 60
FAILURE_COOLDOWN_SECONDS = 60
MAX_RETRIES_PER_PROVIDER = 1

DEFAULT_PROVIDER_MODULES: list[tuple[str, str]] = [
    ("polygon_fx", "modules.forex.providers.polygon_forex_provider"),
    ("twelvedata_fx", "modules.forex.providers.twelvedata_forex_provider"),
    ("marketdata_fx", "modules.forex.providers.marketdata_forex_provider"),
    ("finnhub_fx", "modules.forex.providers.finnhub_forex_provider"),
    ("alpha_vantage_fx", "modules.forex.providers.alpha_vantage_forex_provider"),
    ("frankfurter", "modules.forex.providers.frankfurter_provider"),
    ("exchangerate_host", "modules.forex.providers.exchangerate_provider"),
    ("ecb", "modules.forex.providers.ecb_provider"),
    ("yahoo_fx", "modules.forex.providers.yahoo_forex_provider"),
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().replace(microsecond=0).isoformat()


def safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None or value == "":
            return default
        out = float(value)
        if math.isnan(out) or math.isinf(out):
            return default
        return out
    except Exception:
        return default


def normalize_pair(pair: str) -> str:
    text = str(pair or "").upper().strip()
    text = text.replace("-", "/").replace("_", "/").replace(" ", "")
    if "/" in text:
        left, right = text.split("/", 1)
        return f"{left[:3]}/{right[:3]}"
    if len(text) >= 6:
        return f"{text[:3]}/{text[3:6]}"
    return text


def pair_to_symbol(pair: str) -> str:
    return normalize_pair(pair).replace("/", "")


def split_pair(pair: str) -> tuple[str, str]:
    pair = normalize_pair(pair)
    if "/" in pair:
        left, right = pair.split("/", 1)
        return left[:3], right[:3]
    if len(pair) >= 6:
        return pair[:3], pair[3:6]
    return pair[:3], ""


def is_rate_limit_error(exc: Any) -> bool:
    text = str(exc or "").lower()
    return any(x in text for x in ("rate limit", "rate_limit", "429", "too many requests", "quota", "throttle"))


def is_auth_error(exc: Any) -> bool:
    text = str(exc or "").lower()
    return any(x in text for x in ("401", "403", "unauthorized", "forbidden", "invalid api", "no api key", "not configured"))


def build_quote_payload(
    pair: str,
    provider: str = "router",
    *,
    bid: Any = None,
    ask: Any = None,
    mid: Any = None,
    last: Any = None,
    spread: Any = None,
    timestamp: Any = None,
    source: Optional[str] = None,
    error: Optional[str] = None,
    raw: Optional[dict] = None,
    failover_errors: Optional[list[str]] = None,
) -> dict:
    pair = normalize_pair(pair)
    base, quote = split_pair(pair)

    bid_f = safe_float(bid)
    ask_f = safe_float(ask)
    mid_f = safe_float(mid)
    last_f = safe_float(last)

    if mid_f is None and bid_f is not None and ask_f is not None and bid_f > 0 and ask_f > 0:
        mid_f = (bid_f + ask_f) / 2.0

    if last_f is None and mid_f is not None:
        last_f = mid_f
    if mid_f is None and last_f is not None:
        mid_f = last_f

    spread_f = safe_float(spread)
    if spread_f is None and bid_f is not None and ask_f is not None and ask_f >= bid_f:
        spread_f = ask_f - bid_f

    if isinstance(timestamp, datetime):
        timestamp = timestamp.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    elif not timestamp:
        timestamp = utc_now_iso()
    else:
        timestamp = str(timestamp)

    provider = str(provider or "router").lower().strip()

    return {
        "pair": pair,
        "symbol": pair_to_symbol(pair),
        "base": base,
        "quote": quote,
        "bid": bid_f,
        "ask": ask_f,
        "mid": mid_f,
        "last": last_f,
        "spread": spread_f,
        "timestamp": timestamp,
        "provider": provider,
        "source": str(source or provider).lower(),
        "error": error,
        "failover_errors": list(failover_errors or []),
        "raw": raw or {},
    }


def quote_has_usable_rate(payload: Any) -> bool:
    if not isinstance(payload, dict) or payload.get("error"):
        return False
    for key in ("mid", "last", "bid", "ask", "rate", "price", "close"):
        value = safe_float(payload.get(key))
        if value is not None and value > 0:
            return True
    return False


def normalize_provider_response(pair: str, provider: str, response: Any, errors: Optional[list[str]] = None) -> dict:
    if isinstance(response, (int, float)):
        return build_quote_payload(pair, provider, mid=response, last=response, raw={"value": response}, failover_errors=errors)

    if not isinstance(response, dict):
        return build_quote_payload(pair, provider, error=f"{provider} returned invalid response", raw={"response": str(response)[:500]}, failover_errors=errors)

    if response.get("error"):
        return build_quote_payload(pair, provider, error=str(response.get("error")), raw=response, failover_errors=errors)

    base, quote = split_pair(pair)

    bid = response.get("bid")
    ask = response.get("ask")
    mid = (
        response.get("mid")
        or response.get("rate")
        or response.get("price")
        or response.get("last")
        or response.get("close")
        or response.get("value")
    )
    last = response.get("last") or response.get("price") or response.get("rate") or mid
    spread = response.get("spread")

    rates = response.get("rates")
    if mid is None and isinstance(rates, dict):
        mid = rates.get(quote) or rates.get(pair_to_symbol(pair)) or rates.get(normalize_pair(pair))

    for nested_key in ("quote", "data", "result"):
        nested = response.get(nested_key)
        if mid is None and isinstance(nested, dict):
            mid = nested.get("mid") or nested.get("rate") or nested.get("price") or nested.get("last") or nested.get("close")

    return build_quote_payload(
        pair,
        provider,
        bid=bid,
        ask=ask,
        mid=mid,
        last=last,
        spread=spread,
        timestamp=response.get("timestamp") or response.get("time") or response.get("datetime") or response.get("updated_at"),
        source=response.get("source") or provider,
        raw=response,
        failover_errors=errors,
    )


@dataclass
class ForexProviderStatus:
    provider: str
    module_path: Optional[str] = None
    enabled: bool = True
    priority: int = 100
    health_score: float = 100.0
    success_count: int = 0
    failure_count: int = 0
    rate_limit_count: int = 0
    auth_error_count: int = 0
    invalid_response_count: int = 0
    avg_latency_ms: float = 0.0
    requests_today: int = 0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    cooldown_until: Optional[datetime] = None
    last_error: Optional[str] = None

    def as_row(self) -> dict:
        row = asdict(self)
        for key in ("last_success", "last_failure", "cooldown_until"):
            if isinstance(row.get(key), datetime):
                row[key] = row[key].astimezone(timezone.utc).replace(microsecond=0).isoformat()
        row["health_score"] = round(float(row["health_score"]), 2)
        row["avg_latency_ms"] = round(float(row["avg_latency_ms"]), 2)
        return row


class ForexProviderRouter:
    def __init__(self, cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS):
        self.cache_ttl_seconds = int(cache_ttl_seconds)
        self._lock = Lock()
        self._quote_cache: dict[str, dict] = {}
        self._providers: dict[str, ForexProviderStatus] = {}
        self._provider_functions: dict[str, Callable[..., Any]] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        for priority, (name, module_path) in enumerate(DEFAULT_PROVIDER_MODULES, start=1):
            self.register_provider(name, module_path=module_path, priority=priority, ignore_import_errors=True)

    @staticmethod
    def _provider_key(provider_name: str) -> str:
        return str(provider_name or "").strip().lower()

    def _load_provider_function(self, module_path: str) -> Callable[..., Any]:
        module = importlib.import_module(module_path)

        for fn_name in ("get_quote", "get_forex_quote", "quote", "fetch_quote"):
            fn = getattr(module, fn_name, None)
            if callable(fn):
                return fn

        rate_fn = getattr(module, "get_rate", None)
        if callable(rate_fn):
            def rate_adapter(pair: str) -> Any:
                base, quote = split_pair(pair)
                return rate_fn(base, quote)
            return rate_adapter

        raise AttributeError(f"{module_path} has no Forex quote function")

    def register_provider(
        self,
        provider_name: str,
        provider_fn: Optional[Callable[..., Any]] = None,
        *,
        module_path: Optional[str] = None,
        priority: int = 100,
        enabled: bool = True,
        ignore_import_errors: bool = False,
    ) -> None:
        name = self._provider_key(provider_name)

        fn = provider_fn
        if fn is None and module_path:
            try:
                fn = self._load_provider_function(module_path)
            except Exception:
                if not ignore_import_errors:
                    raise
                fn = None

        with self._lock:
            self._providers[name] = self._providers.get(name) or ForexProviderStatus(provider=name)
            self._providers[name].module_path = module_path or self._providers[name].module_path
            self._providers[name].priority = int(priority)
            self._providers[name].enabled = bool(enabled)
            if fn is not None:
                self._provider_functions[name] = fn

    def unregister_provider(self, provider_name: str) -> None:
        name = self._provider_key(provider_name)
        with self._lock:
            self._providers.pop(name, None)
            self._provider_functions.pop(name, None)

    def get_provider(self, provider_name: str) -> Optional[ForexProviderStatus]:
        return self._providers.get(self._provider_key(provider_name))

    def all_providers(self) -> list[ForexProviderStatus]:
        return list(self._providers.values())

    def enable_provider(self, provider_name: str) -> None:
        provider = self.get_provider(provider_name)
        if provider:
            provider.enabled = True

    def disable_provider(self, provider_name: str) -> None:
        provider = self.get_provider(provider_name)
        if provider:
            provider.enabled = False

    def reset_health(self, provider_name: str) -> None:
        provider = self.get_provider(provider_name)
        if not provider:
            return
        provider.health_score = 100.0
        provider.failure_count = 0
        provider.rate_limit_count = 0
        provider.auth_error_count = 0
        provider.invalid_response_count = 0
        provider.cooldown_until = None
        provider.last_error = None

    def is_available(self, provider_name: str) -> bool:
        provider = self.get_provider(provider_name)
        if not provider or not provider.enabled:
            return False

        if provider.cooldown_until and provider.cooldown_until > utc_now():
            return False

        if provider.provider not in self._provider_functions and provider.module_path:
            try:
                self._provider_functions[provider.provider] = self._load_provider_function(provider.module_path)
            except Exception as exc:
                provider.last_error = str(exc)
                return False

        return provider.provider in self._provider_functions

    def get_ranked_providers(self, allowed: Optional[list[str]] = None) -> list[ForexProviderStatus]:
        allowed_set = {self._provider_key(p) for p in allowed} if allowed else None
        rows = []
        for provider in self._providers.values():
            if allowed_set and provider.provider not in allowed_set:
                continue
            if self.is_available(provider.provider):
                rows.append(provider)
        rows.sort(key=lambda p: (-p.health_score, p.priority, p.avg_latency_ms, p.provider))
        return rows

    def _cache_key(self, pair: str) -> str:
        return pair_to_symbol(pair)

    def get_cached_quote(self, pair: str) -> Optional[dict]:
        key = self._cache_key(pair)
        entry = self._quote_cache.get(key)
        if not entry:
            return None
        age = time.time() - float(entry.get("ts", 0))
        if age > self.cache_ttl_seconds:
            self._quote_cache.pop(key, None)
            return None
        payload = entry.get("data")
        return dict(payload) if quote_has_usable_rate(payload) else None

    def set_cached_quote(self, pair: str, payload: dict) -> dict:
        self._quote_cache[self._cache_key(pair)] = {"ts": time.time(), "data": dict(payload)}
        return payload

    def clear_cache(self) -> None:
        self._quote_cache.clear()

    def mark_success(self, provider_name: str, latency_ms: float = 0.0) -> None:
        provider = self.get_provider(provider_name)
        if not provider:
            return
        with self._lock:
            provider.success_count += 1
            provider.requests_today += 1
            provider.last_success = utc_now()
            provider.last_error = None
            if latency_ms > 0:
                provider.avg_latency_ms = latency_ms if provider.avg_latency_ms <= 0 else provider.avg_latency_ms * 0.90 + latency_ms * 0.10
            provider.health_score = min(100.0, provider.health_score + 1.0)

    def mark_failure(self, provider_name: str, error: Optional[str] = None, cooldown_seconds: int = 0) -> None:
        provider = self.get_provider(provider_name)
        if not provider:
            return
        with self._lock:
            provider.failure_count += 1
            provider.last_failure = utc_now()
            provider.last_error = str(error or "")
            provider.health_score = max(0.0, provider.health_score - 5.0)
            if is_auth_error(error):
                provider.auth_error_count += 1
                provider.health_score = max(0.0, provider.health_score - 25.0)
                provider.cooldown_until = utc_now() + timedelta(seconds=max(cooldown_seconds, FAILURE_COOLDOWN_SECONDS * 10))
            elif cooldown_seconds:
                provider.cooldown_until = utc_now() + timedelta(seconds=int(cooldown_seconds))

    def mark_invalid_response(self, provider_name: str, error: Optional[str] = None) -> None:
        provider = self.get_provider(provider_name)
        if provider:
            provider.invalid_response_count += 1
        self.mark_failure(provider_name, error or "invalid response")

    def mark_rate_limited(self, provider_name: str, error: Optional[str] = None, cooldown_seconds: int = RATE_LIMIT_COOLDOWN_SECONDS) -> None:
        provider = self.get_provider(provider_name)
        if not provider:
            return
        with self._lock:
            provider.rate_limit_count += 1
            provider.failure_count += 1
            provider.last_failure = utc_now()
            provider.last_error = str(error or "rate limited")
            provider.cooldown_until = utc_now() + timedelta(seconds=int(cooldown_seconds))
            provider.health_score = max(0.0, provider.health_score - 25.0)

    def get_quote(
        self,
        pair: str,
        *,
        force_refresh: bool = False,
        allowed_providers: Optional[list[str]] = None,
        raise_on_failure: bool = False,
    ) -> dict:
        pair = normalize_pair(pair)
        if not pair or "/" not in pair:
            return build_quote_payload(pair, "router", error="Valid Forex pair is required")

        if not force_refresh:
            cached = self.get_cached_quote(pair)
            if cached:
                return cached

        errors: list[str] = []
        ranked = self.get_ranked_providers(allowed=allowed_providers)

        for provider in ranked:
            fn = self._provider_functions.get(provider.provider)
            if not callable(fn):
                errors.append(f"{provider.provider}: provider function unavailable")
                continue

            for attempt in range(max(1, MAX_RETRIES_PER_PROVIDER)):
                started = time.perf_counter()
                try:
                    response = fn(pair)
                    latency_ms = (time.perf_counter() - started) * 1000.0
                    payload = normalize_provider_response(pair, provider.provider, response, errors)

                    if quote_has_usable_rate(payload):
                        self.mark_success(provider.provider, latency_ms=latency_ms)
                        payload["provider"] = provider.provider
                        payload["source"] = payload.get("source") or provider.provider
                        payload["failover_errors"] = list(errors)
                        return self.set_cached_quote(pair, payload)

                    msg = payload.get("error") or f"{provider.provider} returned no usable rate"
                    errors.append(f"{provider.provider}: {msg}")
                    self.mark_invalid_response(provider.provider, msg)

                except Exception as exc:
                    msg = str(exc)
                    errors.append(f"{provider.provider}: {msg}")
                    if is_rate_limit_error(msg):
                        self.mark_rate_limited(provider.provider, msg)
                        break
                    self.mark_failure(provider.provider, msg)
                    if is_auth_error(msg):
                        break
                    if attempt + 1 < max(1, MAX_RETRIES_PER_PROVIDER):
                        time.sleep(0.25)

        payload = build_quote_payload(
            pair,
            "router",
            error=f"No Forex provider returned a usable rate for {pair}",
            failover_errors=errors,
        )
        if raise_on_failure:
            raise RuntimeError(f"{payload['error']}: {errors}")
        return payload

    def get_quotes(self, pairs: Iterable[str], *, force_refresh: bool = False, allowed_providers: Optional[list[str]] = None) -> dict[str, dict]:
        return {
            normalize_pair(pair): self.get_quote(pair, force_refresh=force_refresh, allowed_providers=allowed_providers)
            for pair in pairs
        }

    def get_latest_price(self, pair: str, **kwargs) -> Optional[float]:
        payload = self.get_quote(pair, **kwargs)
        return safe_float(payload.get("mid") or payload.get("last"))

    def get_latest_prices(self, pairs: Iterable[str], **kwargs) -> dict[str, Optional[float]]:
        return {
            pair: safe_float(payload.get("mid") or payload.get("last"))
            for pair, payload in self.get_quotes(pairs, **kwargs).items()
        }

    def get_status_rows(self) -> list[dict]:
        return [provider.as_row() for provider in self.all_providers()]

    def get_provider_snapshot(self) -> list[dict]:
        return self.get_status_rows()

    def cache_status(self) -> dict:
        now = time.time()
        rows = []
        for key, entry in self._quote_cache.items():
            data = entry.get("data") or {}
            age = now - float(entry.get("ts", 0))
            rows.append({
                "key": key,
                "pair": data.get("pair"),
                "provider": data.get("provider"),
                "mid": data.get("mid"),
                "age_seconds": round(age, 2),
                "expired": age > self.cache_ttl_seconds,
            })
        return {"ttl_seconds": self.cache_ttl_seconds, "entries": len(rows), "rows": rows}

    def diagnostics(self) -> dict:
        providers = self.all_providers()
        return {
            "summary": {
                "providers": len(providers),
                "enabled": len([p for p in providers if p.enabled]),
                "available": len(self.get_ranked_providers()),
                "cache_entries": len(self._quote_cache),
                "generated_at": utc_now_iso(),
            },
            "providers": self.get_status_rows(),
            "ranked": [p.as_row() for p in self.get_ranked_providers()],
            "cache": self.cache_status(),
        }


_ROUTER: Optional[ForexProviderRouter] = None


def get_forex_provider_router() -> ForexProviderRouter:
    global _ROUTER
    if _ROUTER is None:
        _ROUTER = ForexProviderRouter()
    return _ROUTER


def reset_forex_provider_router() -> ForexProviderRouter:
    global _ROUTER
    _ROUTER = ForexProviderRouter()
    return _ROUTER


def get_forex_quote_from_router(pair: str, force_refresh: bool = False, allowed_providers: Optional[list[str]] = None) -> dict:
    return get_forex_provider_router().get_quote(
        pair,
        force_refresh=force_refresh,
        allowed_providers=allowed_providers,
    )


def get_forex_quotes_from_router(pairs: Iterable[str], force_refresh: bool = False, allowed_providers: Optional[list[str]] = None) -> dict[str, dict]:
    return get_forex_provider_router().get_quotes(
        pairs,
        force_refresh=force_refresh,
        allowed_providers=allowed_providers,
    )


def get_forex_latest_price(pair: str, force_refresh: bool = False) -> Optional[float]:
    return get_forex_provider_router().get_latest_price(pair, force_refresh=force_refresh)


def get_forex_latest_prices(pairs: Iterable[str], force_refresh: bool = False) -> dict[str, Optional[float]]:
    return get_forex_provider_router().get_latest_prices(pairs, force_refresh=force_refresh)


def clear_forex_quote_router_cache() -> None:
    get_forex_provider_router().clear_cache()


def get_forex_provider_status_rows() -> list[dict]:
    return get_forex_provider_router().get_status_rows()
