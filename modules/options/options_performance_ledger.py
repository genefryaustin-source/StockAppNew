"""
modules/options/options_performance_ledger.py

Phase 8 — Options Learning & Performance Intelligence
Lightweight performance ledger utilities. Designed to work without a database by
using Streamlit session_state when available, while remaining import-safe for
batch tests and future DB persistence.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state() -> dict[str, Any]:
    try:
        import streamlit as st
        if "options_performance_ledger" not in st.session_state:
            st.session_state["options_performance_ledger"] = []
        return {"items": st.session_state["options_performance_ledger"]}
    except Exception:
        if not hasattr(_state, "_items"):
            _state._items = []  # type: ignore[attr-defined]
        return {"items": _state._items}  # type: ignore[attr-defined]


def record_trade_outcome(
    ticker: str,
    strategy: str,
    thesis: str = "",
    entry_price: float = 0.0,
    exit_price: float | None = None,
    qty: int = 1,
    status: str = "open",
    source: str = "manual",
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    qty = int(qty or 1)
    exit_price = exit_price if exit_price is not None else entry_price
    pnl = (float(exit_price or 0) - float(entry_price or 0)) * qty * 100
    rec = {
        "id": str(uuid.uuid4()),
        "ticker": ticker.upper(),
        "strategy": strategy,
        "thesis": thesis,
        "entry_price": float(entry_price or 0),
        "exit_price": float(exit_price or 0),
        "qty": qty,
        "pnl": round(pnl, 2),
        "return_pct": round((pnl / max(1.0, abs(float(entry_price or 0) * qty * 100))) * 100, 2),
        "status": status,
        "source": source,
        "tags": tags or [],
        "metadata": metadata or {},
        "created_at": _now(),
        "updated_at": _now(),
    }
    _state()["items"].append(rec)
    return rec


def get_performance_records(ticker: str | None = None, limit: int = 250) -> list[dict[str, Any]]:
    rows = list(_state()["items"])
    if ticker:
        rows = [r for r in rows if str(r.get("ticker", "")).upper() == ticker.upper()]
    rows.sort(key=lambda r: str(r.get("created_at", "")), reverse=True)
    return rows[:limit]


def seed_sample_outcomes(ticker: str) -> list[dict[str, Any]]:
    if get_performance_records(ticker):
        return get_performance_records(ticker)
    samples = [
        ("Bull Put Spread", "Dealer support and positive premium flow", 1.15, 0.35, 3, "closed", ["income", "dealer"]),
        ("Long Straddle", "Pre-event volatility expansion", 4.20, 5.10, 1, "closed", ["volatility", "event"]),
        ("Covered Call", "Income harvest against long shares", 2.05, 0.80, 2, "closed", ["income"]),
        ("Bear Call Spread", "Overhead gamma wall rejection", 1.40, 2.10, 2, "closed", ["dealer", "risk"]),
        ("Bull Call Spread", "Smart-money call premium concentration", 2.65, 4.15, 1, "closed", ["smart_money"]),
    ]
    for strategy, thesis, entry, exit_, qty, status, tags in samples:
        record_trade_outcome(ticker, strategy, thesis, entry, exit_, qty, status, "sample", tags)
    return get_performance_records(ticker)
