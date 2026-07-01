"""
modules/forex/forex_runtime_telemetry_engine.py

Sprint 30 Phase 1 - Runtime Telemetry Engine.
Captures structured telemetry after each Forex runtime build.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from modules.db.core import new_db_session

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _safe_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    if isinstance(value, set):
        return sorted(list(value))
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    try:
        json.dumps(value)
        return value
    except Exception:
        return str(value)


def _components(context: Any) -> Dict[str, bool]:
    return {
        "provider_health": getattr(context, "provider_health", None) is not None,
        "quotes": getattr(context, "quotes", None) is not None,
        "alpha": getattr(context, "alpha", None) is not None,
        "currency_strength": getattr(context, "currency_strength", None) is not None,
        "sentiment": getattr(context, "sentiment", None) is not None,
        "macro": getattr(context, "macro", None) is not None,
        "portfolio": getattr(context, "portfolio", None) is not None,
        "carry": getattr(context, "carry", None) is not None,
        "central_banks": getattr(context, "central_banks", None) is not None,
        "execution": getattr(context, "execution", None) is not None,
        "institutional": getattr(context, "institutional", None) is not None,
    }


def _component_score(components: Dict[str, bool]) -> float:
    if not components:
        return 0.0
    return round((sum(1 for v in components.values() if v) / len(components)) * 100.0, 2)


def _runtime_health(
    metadata: Dict[str, Any],
    components: Dict[str, bool],
    provider_failures: List[str],
    quote_count: int,
    failed_quote_count: int,
) -> float:
    score = 100.0
    runtime_ms = _safe_float(metadata.get("runtime_total_ms"))
    quote_ms = _safe_float(metadata.get("quotes_ms"))
    portfolio_ms = _safe_float(metadata.get("portfolio_ms"))

    score -= max(0.0, 100.0 - _component_score(components)) * 0.35

    if quote_count > 0:
        score -= (failed_quote_count / quote_count) * 25.0
    elif components.get("quotes"):
        score -= 15.0

    score -= min(15.0, len(provider_failures) * 2.0)

    if runtime_ms > 5000:
        score -= 10.0
    elif runtime_ms > 3500:
        score -= 5.0

    if quote_ms > 4000:
        score -= 10.0
    elif quote_ms > 2500:
        score -= 4.0

    if portfolio_ms > 1000:
        score -= 5.0

    return round(max(0.0, min(100.0, score)), 2)


@dataclass
class ForexRuntimeTelemetryRecord:
    id: str
    created_at: str
    runtime_id: Optional[str]
    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    runtime_ms: float = 0.0
    quote_ms: float = 0.0
    alpha_ms: float = 0.0
    currency_strength_ms: float = 0.0
    sentiment_ms: float = 0.0
    macro_ms: float = 0.0
    portfolio_ms: float = 0.0
    carry_ms: float = 0.0
    central_banks_ms: float = 0.0
    execution_ms: float = 0.0
    institutional_ms: float = 0.0

    quote_count: int = 0
    failed_quote_count: int = 0
    batch_requests: int = 0
    individual_requests: int = 0

    provider_usage: Dict[str, Any] = field(default_factory=dict)
    provider_latency: Dict[str, Any] = field(default_factory=dict)
    provider_failures: List[str] = field(default_factory=list)
    cache_stats: Dict[str, Any] = field(default_factory=dict)
    components: Dict[str, bool] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    runtime_health: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return _json_safe(asdict(self))


class ForexRuntimeTelemetryEngine:
    def __init__(self, db: Any = None, max_memory_records: int = 250):
        self.db = db
        self.max_memory_records = int(max_memory_records)
        #self._records: List[Dict[str, Any]] = []
        self._records = []

    def set_db(self, db: Any) -> "ForexRuntimeTelemetryEngine":
        self.db = db
        return self

    def build_record(self, context: Any) -> ForexRuntimeTelemetryRecord:
        metadata = _safe_dict(getattr(context, "metadata", {}))
        diagnostics = _safe_dict(getattr(context, "diagnostics", {}))
        components = _components(context)

        quotes = getattr(context, "quotes", None)
        quote_count = len(quotes) if isinstance(quotes, dict) else 0
        failed_quote_count = 0
        if isinstance(quotes, dict):
            failed_quote_count = sum(
                1 for payload in quotes.values()
                if isinstance(payload, dict) and payload.get("error")
            )

        provider_usage = _safe_dict(getattr(context, "provider_usage", {}))
        provider_latency = _safe_dict(getattr(context, "provider_latency", {}))
        provider_failures = sorted(list(getattr(context, "failed_providers", set()) or []))

        cache_stats: Dict[str, Any] = {}
        try:
            from modules.forex.providers.forex_quote_cache import get_forex_quote_cache
            cache_stats = _safe_dict(get_forex_quote_cache().stats())
        except Exception as exc:
            cache_stats = {"error": repr(exc)}

        record = ForexRuntimeTelemetryRecord(
            id=str(uuid.uuid4()),
            created_at=_utc_now_iso(),
            runtime_id=metadata.get("runtime_id"),
            tenant_id=getattr(context, "tenant_id", None),
            user_id=getattr(context, "user_id", None),
            portfolio_id=getattr(context, "portfolio_id", None),
            runtime_ms=_safe_float(metadata.get("runtime_total_ms")),
            quote_ms=_safe_float(metadata.get("quotes_ms")),
            alpha_ms=_safe_float(metadata.get("alpha_ms")),
            currency_strength_ms=_safe_float(metadata.get("currency_strength_ms")),
            sentiment_ms=_safe_float(metadata.get("sentiment_ms")),
            macro_ms=_safe_float(metadata.get("macro_ms")),
            portfolio_ms=_safe_float(metadata.get("portfolio_ms")),
            carry_ms=_safe_float(metadata.get("carry_ms")),
            central_banks_ms=_safe_float(metadata.get("central_banks_ms")),
            execution_ms=_safe_float(metadata.get("execution_ms")),
            institutional_ms=_safe_float(metadata.get("institutional_ms")),
            quote_count=quote_count,
            failed_quote_count=failed_quote_count,
            batch_requests=int(getattr(context, "batch_requests", 0) or 0),
            individual_requests=int(getattr(context, "individual_requests", 0) or 0),
            provider_usage=provider_usage,
            provider_latency=provider_latency,
            provider_failures=provider_failures,
            cache_stats=cache_stats,
            components=components,
            metadata=metadata,
            diagnostics=diagnostics,
        )

        record.runtime_health = _runtime_health(
            metadata=metadata,
            components=components,
            provider_failures=provider_failures,
            quote_count=quote_count,
            failed_quote_count=failed_quote_count,
        )
        return record

    def record_runtime(self, context: Any) -> Dict[str, Any]:
        record = self.build_record(context).to_dict()
        self._records.append(record)
        if len(self._records) > self.max_memory_records:
            self._records = self._records[-self.max_memory_records:]

        self._persist_record(record)

        print("=" * 80)
        print("FOREX RUNTIME TELEMETRY RECORDED")
        print("runtime_id     :", record.get("runtime_id"))
        print("runtime_ms     :", record.get("runtime_ms"))
        print("quote_ms       :", record.get("quote_ms"))
        print("portfolio_ms   :", record.get("portfolio_ms"))
        print("runtime_health :", record.get("runtime_health"))
        print("quote_count    :", record.get("quote_count"))
        print("failed_quotes  :", record.get("failed_quote_count"))
        print("=" * 80)

        return record

    def _persist_record(
            self,
            record: Dict[str, Any],
    ) -> None:

        #
        # Use supplied DB or create one.
        #
        if self.db is None:
            db = new_db_session()
            owns_session = True
        else:
            db = self.db
            owns_session = False

        try:

            from sqlalchemy import text

            params = dict(record)
            for key in (
                "provider_usage",
                "provider_latency",
                "provider_failures",
                "cache_stats",
                "components",
                "metadata",
                "diagnostics",
            ):
                params[key] = json.dumps(record.get(key, {}))

            self.db.execute(
                text(
                    """
                    INSERT INTO forex_runtime_history (
                        id, created_at, tenant_id, user_id, portfolio_id,
                        runtime_id, runtime_ms, quote_ms, alpha_ms,
                        currency_strength_ms, sentiment_ms, macro_ms,
                        portfolio_ms, carry_ms, central_banks_ms,
                        execution_ms, institutional_ms, quote_count,
                        failed_quote_count, batch_requests, individual_requests,
                        provider_usage, provider_latency, provider_failures,
                        cache_stats, components, metadata, diagnostics,
                        runtime_health
                    )
                    VALUES (
                        :id, :created_at, :tenant_id, :user_id, :portfolio_id,
                        :runtime_id, :runtime_ms, :quote_ms, :alpha_ms,
                        :currency_strength_ms, :sentiment_ms, :macro_ms,
                        :portfolio_ms, :carry_ms, :central_banks_ms,
                        :execution_ms, :institutional_ms, :quote_count,
                        :failed_quote_count, :batch_requests, :individual_requests,
                        CAST(:provider_usage AS JSONB),
                        CAST(:provider_latency AS JSONB),
                        CAST(:provider_failures AS JSONB),
                        CAST(:cache_stats AS JSONB),
                        CAST(:components AS JSONB),
                        CAST(:metadata AS JSONB),
                        CAST(:diagnostics AS JSONB),
                        :runtime_health
                    )
                    """
                ),
                params,
            )
            self.db.commit()


        except Exception:

            db.rollback()

            raise


        finally:

            if owns_session:
                db.close()

    def latest(self) -> Optional[Dict[str, Any]]:
        return self._records[-1] if self._records else None

    def history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._records[-int(limit):]

    def summary(self) -> Dict[str, Any]:
        if not self._records:
            return {"status": "EMPTY", "records": 0, "latest": None}

        count = len(self._records)
        latest = self.latest() or {}
        avg_runtime = sum(_safe_float(r.get("runtime_ms")) for r in self._records) / count
        avg_quote = sum(_safe_float(r.get("quote_ms")) for r in self._records) / count
        avg_health = sum(_safe_float(r.get("runtime_health")) for r in self._records) / count

        return {
            "status": "READY",
            "records": count,
            "latest_runtime_id": latest.get("runtime_id"),
            "latest_runtime_ms": latest.get("runtime_ms"),
            "latest_quote_ms": latest.get("quote_ms"),
            "latest_runtime_health": latest.get("runtime_health"),
            "avg_runtime_ms": round(avg_runtime, 2),
            "avg_quote_ms": round(avg_quote, 2),
            "avg_runtime_health": round(avg_health, 2),
        }


_ENGINE: Optional[ForexRuntimeTelemetryEngine] = None


def get_runtime_telemetry_engine(db: Any = None) -> ForexRuntimeTelemetryEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = ForexRuntimeTelemetryEngine(db=db)
    elif db is not None:
        _ENGINE.set_db(db)
    return _ENGINE


def record_forex_runtime_telemetry(context: Any, db: Any = None) -> Dict[str, Any]:
    return get_runtime_telemetry_engine(db=db).record_runtime(context)
