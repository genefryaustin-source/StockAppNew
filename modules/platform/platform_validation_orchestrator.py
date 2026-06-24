from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from modules.equities.equities_validation_engine import (
    run_equities_validation,
)

from modules.options.options_validation_orchestrator import (
    run_full_options_validation,
)

from modules.portfolio.portfolio_validation_engine import (
    run_portfolio_validation,
)

from modules.providers.provider_validation_engine import (
    run_provider_validation,
)


def _engine_status(result: dict) -> str:
    return str(
        result.get("status", "WARN")
    ).upper()


def _engine_score(result: dict) -> float:
    try:
        return float(result.get("score", 0))
    except Exception:
        return 0.0


def _extract_totals(result: dict) -> dict:
    totals = result.get("totals", {})

    return {
        "PASS": int(totals.get("PASS", 0)),
        "WARN": int(totals.get("WARN", 0)),
        "FAIL": int(totals.get("FAIL", 0)),
    }


def _overall_status(
    pass_count: int,
    warn_count: int,
    fail_count: int,
) -> str:

    if fail_count > 0:
        return "FAIL"

    if warn_count > 0:
        return "WARN"

    return "PASS"


def _overall_score(
    pass_count: int,
    warn_count: int,
    fail_count: int,
) -> float:

    total = pass_count + warn_count + fail_count

    if total <= 0:
        return 0.0

    return round(
        (
            pass_count +
            (warn_count * 0.5)
        )
        /
        total
        *
        100.0,
        2,
    )


def run_platform_validation(
    db: Any,
    tenant_id: str | None = None,
) -> dict:

    started_at = datetime.now(
        timezone.utc
    ).isoformat()

    equities_result = run_equities_validation(
        db=db,
        tenant_id=tenant_id,
    )

    options_result = run_full_options_validation()

    portfolio_result = run_portfolio_validation(
        db=db,
        tenant_id=tenant_id,
    )

    provider_result = run_provider_validation(
        db=db,
    )

    engine_results = {
        "equities": equities_result,
        "options": options_result,
        "portfolio": portfolio_result,
        "providers": provider_result,
    }

    pass_count = 0
    warn_count = 0
    fail_count = 0

    engine_statuses = {}
    engine_scores = {}

    for engine_name, result in engine_results.items():

        totals = _extract_totals(result)

        pass_count += totals["PASS"]
        warn_count += totals["WARN"]
        fail_count += totals["FAIL"]

        engine_statuses[engine_name] = _engine_status(
            result
        )

        engine_scores[engine_name] = _engine_score(
            result
        )

    score = _overall_score(
        pass_count,
        warn_count,
        fail_count,
    )

    status = _overall_status(
        pass_count,
        warn_count,
        fail_count,
    )

    return {
        "started_at": started_at,
        "finished_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "score": score,
        "status": status,
        "totals": {
            "PASS": pass_count,
            "WARN": warn_count,
            "FAIL": fail_count,
        },
        "engine_statuses": engine_statuses,
        "engine_scores": engine_scores,
        "equities": equities_result,
        "options": options_result,
        "portfolio": portfolio_result,
        "providers": provider_result,
    }