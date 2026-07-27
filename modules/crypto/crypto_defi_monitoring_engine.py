"""
modules/crypto/crypto_defi_monitoring_engine.py

Sprint CR-4: DeFi Intelligence -- TVL Monitoring and Protocol Risk.

TVL decline detection is always available (pure local computation
over TVL history already recorded from the confirmed-free /tvl
endpoint) -- this doesn't depend on any of the genuinely disputed
endpoints (hacks, bridges), so it's the reliable core of Protocol
Risk regardless of how those turn out in the deployed environment.

Hack-history checking is layered on top, defensively: if
fetch_hacks() reports "unavailable", that's surfaced honestly rather
than silently omitted or treated as "no hacks found" (which would be
a meaningfully different, and wrong, claim).
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def check_protocol_tvl(*, db, protocol_slug: str, decline_alert_threshold_pct: float = -20.0) -> Dict[str, Any]:
    """
    Fetches current TVL for a protocol, records it, and flags a
    TVL_DECLINE risk if it dropped by more than
    decline_alert_threshold_pct (a negative number) since the last
    recorded reading -- a real, standard DeFi risk signal: sharp TVL
    decline often precedes or accompanies an exploit, depeg, or loss
    of confidence.
    """
    from modules.crypto.crypto_defi_service import fetch_protocol_tvl
    from modules.crypto.crypto_defi_intelligence_repository import get_crypto_defi_intelligence_repository

    repo = get_crypto_defi_intelligence_repository(db=db)

    result = fetch_protocol_tvl(protocol_slug)
    if result["status"] != "ok":
        return {"status": result["status"], "message": result.get("message")}

    previous = repo.get_latest_tvl(protocol_slug)
    repo.record_tvl(protocol_slug, result["tvl_usd"])

    change_pct = None
    flagged = False
    if previous and previous.get("tvl_usd"):
        prev_tvl = previous["tvl_usd"]
        if prev_tvl > 0:
            change_pct = (result["tvl_usd"] - prev_tvl) / prev_tvl * 100
            if change_pct <= decline_alert_threshold_pct:
                repo.add_risk_flag(
                    protocol_slug=protocol_slug, risk_type="TVL_DECLINE",
                    severity="HIGH" if change_pct <= decline_alert_threshold_pct * 1.5 else "MEDIUM",
                    details={"change_pct": change_pct, "previous_tvl_usd": prev_tvl, "current_tvl_usd": result["tvl_usd"]},
                )
                flagged = True

    return {
        "status": "ok",
        "tvl_usd": result["tvl_usd"],
        "previous_tvl_usd": previous["tvl_usd"] if previous else None,
        "change_pct": change_pct,
        "flagged": flagged,
    }


def check_protocol_hack_history(*, db, protocol_slug: str, protocol_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Checks DefiLlama's hacks dataset for entries matching this
    protocol. Genuinely defensive: if the endpoint reports
    "unavailable" (paywalled), that's returned as-is, not silently
    converted into "no hacks found" -- those are different claims,
    and conflating them would be dishonest about what was actually
    checked.
    """
    from modules.crypto.crypto_defi_service import fetch_hacks
    from modules.crypto.crypto_defi_intelligence_repository import get_crypto_defi_intelligence_repository

    result = fetch_hacks()
    if result["status"] != "ok":
        return {"status": result["status"], "message": result.get("message")}

    name_to_match = (protocol_name or protocol_slug).lower()
    matches = [
        row for row in result["rows"]
        if row.get("name") and name_to_match in row["name"].lower()
    ]

    if matches:
        repo = get_crypto_defi_intelligence_repository(db=db)
        for match in matches:
            repo.add_risk_flag(
                protocol_slug=protocol_slug, risk_type="HACK_HISTORY", severity="HIGH",
                details=match,
            )

    return {"status": "ok", "matches": matches}