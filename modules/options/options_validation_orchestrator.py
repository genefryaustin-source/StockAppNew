"""
modules/options/options_validation_orchestrator.py

Master Options Validation Orchestrator

Aggregates:

    ✓ Chain Validation
    ✓ Greeks Validation
    ✓ Pricing Validation
    ✓ Volatility Validation
    ✓ Liquidity Validation

Produces:

    Overall Score
    Overall Status
    PASS / WARN / FAIL Counts

Used by:
    Options Validation Center
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


# ============================================================
# ENGINE IMPORTS
# ============================================================

from modules.options.options_validation_engine import (
    run_options_validation,
)

from modules.options.options_greeks_validation_engine import (
    run_greeks_validation,
)

from modules.options.options_pricing_validation_engine import (
    run_pricing_validation,
)

from modules.options.options_volatility_validation_engine import (
    run_volatility_validation,
)

from modules.options.options_liquidity_validation_engine import (
    run_liquidity_validation,
)


# ============================================================
# STATUS EXTRACTION
# ============================================================

def _extract_counts(payload: dict[str, Any]) -> dict[str, int]:
    """
    Attempts to normalize PASS/WARN/FAIL counts from
    all validation engines.

    Supports:
        result["totals"]
        result["summary"]
        result["status_summary"]

    Returns:
        {
            "PASS": x,
            "WARN": y,
            "FAIL": z
        }
    """

    counts = {
        "PASS": 0,
        "WARN": 0,
        "FAIL": 0,
    }

    if not isinstance(payload, dict):
        return counts

    # ----------------------------------
    # totals
    # ----------------------------------

    totals = payload.get("totals")

    if isinstance(totals, dict):
        counts["PASS"] += int(totals.get("PASS", 0))
        counts["WARN"] += int(totals.get("WARN", 0))
        counts["FAIL"] += int(totals.get("FAIL", 0))
        return counts

    # ----------------------------------
    # summary
    # ----------------------------------

    summary = payload.get("summary")

    if isinstance(summary, dict):
        counts["PASS"] += int(summary.get("PASS", 0))
        counts["WARN"] += int(summary.get("WARN", 0))
        counts["FAIL"] += int(summary.get("FAIL", 0))
        return counts

    # ----------------------------------
    # status_summary
    # ----------------------------------

    status_summary = payload.get("status_summary")

    if isinstance(status_summary, dict):
        counts["PASS"] += int(status_summary.get("PASS", 0))
        counts["WARN"] += int(status_summary.get("WARN", 0))
        counts["FAIL"] += int(status_summary.get("FAIL", 0))
        return counts

    # ----------------------------------
    # validation_rows fallback
    # ----------------------------------

    rows = payload.get("rows")

    if isinstance(rows, list):

        for row in rows:

            status = str(
                row.get("status", "")
            ).upper()

            if status in counts:
                counts[status] += 1

    return counts


# ============================================================
# SCORE
# ============================================================

def _calculate_score(
    pass_count: int,
    warn_count: int,
    fail_count: int,
) -> float:

    total = (
        pass_count +
        warn_count +
        fail_count
    )

    if total <= 0:
        return 0.0

    score = (
        (
            pass_count +
            (warn_count * 0.50)
        )
        / total
    ) * 100.0

    return round(score, 2)

def _engine_status(counts: dict[str, int]) -> str:
    """
    Convert row-level counts into a single
    engine-level status.
    """

    fail_count = int(counts.get("FAIL", 0))
    warn_count = int(counts.get("WARN", 0))

    if fail_count > 0:
        return "FAIL"

    if warn_count > 0:
        return "WARN"

    return "PASS"
def _calculate_engine_score(
    pass_count: int,
    warn_count: int,
    fail_count: int,
) -> float:

    total = (
        pass_count +
        warn_count +
        fail_count
    )

    if total <= 0:
        return 0.0

    score = (
        (
            pass_count +
            (warn_count * 0.5)
        )
        / total
    ) * 100.0

    return round(score, 2)
# ============================================================
# STATUS
# ============================================================

def _overall_status(score: float) -> str:

    if score >= 90:
        return "PASS"

    if score >= 75:
        return "WARN"

    return "FAIL"


# ============================================================
# MASTER VALIDATION
# ============================================================

def run_full_options_validation(
    ticker: str,
    expiration: str | None = None,
    max_rows: int = 250,
) -> dict[str, Any]:

    started_at = datetime.now(
        timezone.utc
    ).isoformat()

    # =======================================================
    # EXECUTE ENGINES
    # =======================================================

    chain_result = run_options_validation(
        ticker=ticker,
        expiration=expiration,
    )

    greeks_result = run_greeks_validation(
        ticker=ticker,
        expiration=expiration,
    )

    pricing_result = run_pricing_validation(
        ticker=ticker,
        expiration=expiration,
        max_rows=max_rows,
    )

    volatility_result = run_volatility_validation(
        ticker=ticker,
        expiration=expiration,
    )

    liquidity_result = run_liquidity_validation(
        ticker=ticker,
        expiration=expiration,
    )

    # =======================================================
    # COUNTS
    # =======================================================

    chain_counts = _extract_counts(chain_result)

    greeks_counts = _extract_counts(
        greeks_result
    )

    pricing_counts = _extract_counts(
        pricing_result
    )

    volatility_counts = _extract_counts(
        volatility_result
    )

    liquidity_counts = _extract_counts(
        liquidity_result
    )

    # ======================================================
    # ENGINE LEVEL STATUS
    # ======================================================

    chain_status = _engine_status(
        chain_counts
    )

    greeks_status = _engine_status(
        greeks_counts
    )

    pricing_status = _engine_status(
        pricing_counts
    )

    volatility_status = _engine_status(
        volatility_counts
    )

    liquidity_status = _engine_status(
        liquidity_counts
    )

    engine_statuses = {
        "chain": chain_status,
        "greeks": greeks_status,
        "pricing": pricing_status,
        "volatility": volatility_status,
        "liquidity": liquidity_status,
    }

    # ======================================================
    # ENGINE COUNTS
    # ======================================================

    total_pass = sum(
        1
        for v in engine_statuses.values()
        if v == "PASS"
    )

    total_warn = sum(
        1
        for v in engine_statuses.values()
        if v == "WARN"
    )

    total_fail = sum(
        1
        for v in engine_statuses.values()
        if v == "FAIL"
    )

    # ======================================================
    # OVERALL SCORE
    # ======================================================

    score = _calculate_engine_score(
        pass_count=total_pass,
        warn_count=total_warn,
        fail_count=total_fail,
    )

    status = _overall_status(score)

    finished_at = datetime.now(
        timezone.utc
    ).isoformat()

    # =======================================================
    # RESPONSE
    # =======================================================

    return {

        "ticker": ticker,

        "expiration": expiration,

        "started_at": started_at,

        "finished_at": finished_at,

        "overall_score": score,

        "overall_status": status,

        "pass_count": total_pass,

        "warn_count": total_warn,

        "fail_count": total_fail,

        "engine_statuses": engine_statuses,

        "engine_counts": {

            "chain": chain_counts,
            "greeks": greeks_counts,
            "pricing": pricing_counts,
            "volatility": volatility_counts,
            "liquidity": liquidity_counts,
        },

        "engines": {

            "chain": chain_result,
            "greeks": greeks_result,
            "pricing": pricing_result,
            "volatility": volatility_result,
            "liquidity": liquidity_result,
        },
    }
