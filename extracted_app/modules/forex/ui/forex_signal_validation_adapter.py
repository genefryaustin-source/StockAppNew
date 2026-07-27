# ============================================================
# File: modules/forex/ui/forex_signal_validation_adapter.py
#
# Sprint 24.1
# Institutional Signal Validation Adapter
#
# Purpose
# -------
# Converts any validation engine payload into a single,
# normalized structure consumed by the UI.
#
# This layer intentionally isolates the dashboard from
# engine implementation changes.
# ============================================================

from __future__ import annotations

from typing import Any, Dict, List, Optional
from collections import defaultdict


# ============================================================
# Utility
# ============================================================

def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default

        if isinstance(value, str):
            value = (
                value.replace("%", "")
                .replace("$", "")
                .replace(",", "")
                .strip()
            )

            if value == "":
                return default

        return float(value)

    except Exception:
        return default


def _normalize_pair(pair: str) -> str:
    if not pair:
        return "UNKNOWN"

    pair = pair.upper().replace("-", "").replace("/", "")

    if len(pair) == 6:
        return f"{pair[:3]}/{pair[3:]}"

    return pair


def _walk(node):

    if isinstance(node, dict):
        yield node

        for v in node.values():
            yield from _walk(v)

    elif isinstance(node, list):

        for item in node:
            yield from _walk(item)


# ============================================================
# Signal Extraction
# ============================================================

_SIGNAL_KEYS = (
    "signals",
    "validated_signals",
    "recommendations",
    "trade_candidates",
    "entries",
    "rows",
)


def _find_signal_list(payload: Dict[str, Any]) -> List[Dict]:

    if not isinstance(payload, dict):
        return []

    #
    # Direct search
    #

    for key in _SIGNAL_KEYS:

        if key in payload:

            value = payload[key]

            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]

    #
    # Recursive search
    #

    for node in _walk(payload):

        if not isinstance(node, dict):
            continue

        for key in _SIGNAL_KEYS:

            if key in node and isinstance(node[key], list):
                return [x for x in node[key] if isinstance(x, dict)]

    return []


# ============================================================
# Canonical Signal
# ============================================================

def _canonical_signal(signal: Dict[str, Any]) -> Dict[str, Any]:

    pair = (
        signal.get("pair")
        or signal.get("symbol")
        or signal.get("currency_pair")
        or signal.get("instrument")
        or "UNKNOWN"
    )

    pair = _normalize_pair(pair)

    action = (
        signal.get("signal")
        or signal.get("recommendation")
        or signal.get("action")
        or "WATCH"
    ).upper()

    score = max(
        _safe_float(signal.get("validation_score")),
        _safe_float(signal.get("score")),
        _safe_float(signal.get("composite_score")),
    )

    confidence = max(
        _safe_float(signal.get("confidence")),
        _safe_float(signal.get("confidence_score")),
        score,
    )

    rr = max(
        _safe_float(signal.get("risk_reward")),
        _safe_float(signal.get("rr")),
    )

    return {

        "pair": pair,

        "signal": action,

        "validation_score": round(score, 2),

        "confidence": round(confidence, 2),

        "risk_reward": round(rr, 2),

        "entry": _safe_float(
            signal.get("entry")
            or signal.get("entry_price")
        ),

        "target": _safe_float(
            signal.get("target")
            or signal.get("target_price")
        ),

        "stop": _safe_float(
            signal.get("stop")
            or signal.get("stop_price")
        ),

        "timeframe": (
            signal.get("timeframe")
            or "1H"
        ),

        "strategy": (
            signal.get("strategy")
            or "Institutional"
        ),

        "technical_score": _safe_float(
            signal.get("technical_score")
        ),

        "fundamental_score": _safe_float(
            signal.get("fundamental_score")
        ),

        "macro_score": _safe_float(
            signal.get("macro_score")
        ),

        "sentiment_score": _safe_float(
            signal.get("sentiment_score")
        ),

        "status": (
            signal.get("status")
            or "PENDING"
        ).upper(),
    }


# ============================================================
# Duplicate Consolidation
# ============================================================

def _deduplicate(signals: List[Dict]) -> List[Dict]:

    grouped = defaultdict(list)

    for signal in signals:

        key = (
            signal["pair"],
            signal["signal"],
            signal["timeframe"],
        )

        grouped[key].append(signal)

    merged = []

    for _, rows in grouped.items():

        rows.sort(
            key=lambda x: (
                x["validation_score"],
                x["confidence"],
            ),
            reverse=True,
        )

        merged.append(rows[0])

    merged.sort(
        key=lambda x: (
            x["validation_score"],
            x["confidence"],
        ),
        reverse=True,
    )

    return merged


# ============================================================
# Summary
# ============================================================

def _summary(signals: List[Dict]) -> Dict[str, Any]:

    if not signals:

        return {

            "signal_count": 0,

            "top_signal": None,

            "validation_score": 0,

            "confidence": 0,

            "risk_reward": 0,
        }

    top = signals[0]

    return {

        "signal_count": len(signals),

        "top_signal": top,

        "validation_score": top["validation_score"],

        "confidence": top["confidence"],

        "risk_reward": top["risk_reward"],

        "average_score": round(

            sum(x["validation_score"] for x in signals)
            / len(signals),

            2,
        ),

        "average_confidence": round(

            sum(x["confidence"] for x in signals)
            / len(signals),

            2,
        ),
    }


# ============================================================
# Analytics
# ============================================================

def _analytics(signals: List[Dict]) -> Dict[str, Any]:

    grades = {

        "BUY": 0,

        "SELL": 0,

        "WATCH": 0,
    }

    for s in signals:

        grades.setdefault(s["signal"], 0)

        grades[s["signal"]] += 1

    return {

        "buy_count": grades.get("BUY", 0),

        "sell_count": grades.get("SELL", 0),

        "watch_count": grades.get("WATCH", 0),

        "average_validation": round(

            sum(x["validation_score"] for x in signals)
            / max(1, len(signals)),

            2,
        ),

        "average_confidence": round(

            sum(x["confidence"] for x in signals)
            / max(1, len(signals)),

            2,
        ),
    }


# ============================================================
# Public Adapter
# ============================================================

def normalize_validation_payload(
    payload: Optional[Dict[str, Any]]
) -> Dict[str, Any]:

    payload = payload or {}

    raw = _find_signal_list(payload)

    signals = [

        _canonical_signal(x)

        for x in raw
    ]

    signals = _deduplicate(signals)

    return {

        "signals": signals,

        "summary": _summary(signals),

        "analytics": _analytics(signals),

        "raw_payload": payload,
    }