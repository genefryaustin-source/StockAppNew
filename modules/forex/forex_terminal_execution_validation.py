"""
modules/forex/forex_terminal_execution_validation.py

Small UI helper for Phase 4 validation/testing. Import from the dashboard or an
admin validation page when needed.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def validate_forex_terminal_execution(api: Any, *, pair: str = "EUR/USD", side: str = "BUY", lots: float = 0.01) -> Dict[str, Any]:
    validation = api.validate_order(pair=pair, side=side, lots=lots, order_type="MARKET")
    if not validation.get("valid"):
        return {"status": "VALIDATION_FAILED", "validation": validation}

    result = api.submit_order(pair=pair, side=side, lots=lots, order_type="MARKET")
    snapshot = result.get("snapshot") if isinstance(result, dict) else None
    verification = result.get("verification") if isinstance(result, dict) else None

    return {
        "status": result.get("status") if isinstance(result, dict) else "UNKNOWN",
        "validation": validation,
        "execution": result,
        "verification": verification,
        "snapshot_updated": isinstance(snapshot, dict) and bool(snapshot.get("account")),
    }
