"""
modules/crypto/crypto_reserve_monitoring_service.py

Sprint CR-3: Exchange Intelligence -- Reserve Monitoring.

Confirmed exact format from Etherscan's own docs:
  GET https://api.etherscan.io/v2/api?chainid=...&module=account&action=balance&address=...&tag=latest&apikey=...
  Response: {"status":"1","message":"OK","result":"<balance in wei, as a string>"}

Reuses ETHERSCAN_CHAIN_IDS from crypto_wallet_discovery_engine.py (CR-1)
rather than duplicating the chain-ID mapping.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

ETHERSCAN_V2_BASE_URL = "https://api.etherscan.io/v2/api"

WEI_PER_ETHER = 10 ** 18


def get_native_balance(address: str, chain: str, api_key: str) -> Dict[str, Any]:
    """
    Real network call to Etherscan's V2 balance endpoint -- cannot be
    executed or verified end-to-end from this sandbox
    (api.etherscan.io is outside the allowed fetch domains here, same
    caveat as CR-1's discovery engine). Response parsing below
    matches Etherscan's own confirmed, current schema exactly.
    """
    from modules.crypto.crypto_wallet_discovery_engine import ETHERSCAN_CHAIN_IDS

    chain_id = ETHERSCAN_CHAIN_IDS.get(chain.lower())
    if chain_id is None:
        return {"status": "error", "message": f"Unsupported chain: {chain}"}

    try:
        import urllib.request
        import urllib.parse
        import json

        params = urllib.parse.urlencode({
            "chainid": chain_id,
            "module": "account",
            "action": "balance",
            "address": address,
            "tag": "latest",
            "apikey": api_key,
        })
        url = f"{ETHERSCAN_V2_BASE_URL}?{params}"

        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; WalletIntelligence/1.0)"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read())

        if str(payload.get("status")) != "1":
            return {"status": "error", "message": payload.get("message", "Unknown error")}

        balance_wei = int(payload.get("result", "0"))
        balance_native = balance_wei / WEI_PER_ETHER

        return {"status": "ok", "balance_wei": balance_wei, "balance_native": balance_native}

    except Exception as exc:
        logger.warning("Etherscan balance fetch failed for %s: %s", address, exc)
        return {"status": "error", "message": str(exc)}


def check_reserve_address(
    *, db, reserve_address_id: int, address: str, chain: str, api_key: str,
) -> Dict[str, Any]:
    """
    Fetches the current balance for a reserve address and records it
    into the balance history, returning the change from the previous
    reading (if any) so a caller can flag a significant outflow.
    """
    from modules.crypto.crypto_exchange_intelligence_repository import get_crypto_exchange_intelligence_repository

    repo = get_crypto_exchange_intelligence_repository(db=db)

    result = get_native_balance(address, chain, api_key)
    if result.get("status") != "ok":
        return {"status": "error", "message": result.get("message")}

    previous = repo.get_latest_reserve_balance(reserve_address_id)
    repo.record_reserve_balance(reserve_address_id, result["balance_native"])

    change_pct = None
    if previous and previous.get("balance_native"):
        prev_balance = previous["balance_native"]
        if prev_balance > 0:
            change_pct = (result["balance_native"] - prev_balance) / prev_balance * 100

    return {
        "status": "ok",
        "balance_native": result["balance_native"],
        "previous_balance_native": previous["balance_native"] if previous else None,
        "change_pct": change_pct,
    }


def check_all_reserve_addresses(*, db, tenant_id: Optional[str], api_key: str, outflow_alert_threshold_pct: float = -10.0) -> Dict[str, Any]:
    """
    Checks every registered reserve address for the tenant, records
    its balance, and flags any address whose balance dropped by more
    than outflow_alert_threshold_pct (a negative number, e.g. -10.0
    means "flag if the balance fell by more than 10%") since its last
    recorded reading.
    """
    from modules.crypto.crypto_exchange_intelligence_repository import get_crypto_exchange_intelligence_repository

    repo = get_crypto_exchange_intelligence_repository(db=db)
    reserves = repo.list_reserve_addresses(tenant_id=tenant_id)

    checked = 0
    alerts = []
    errors = []

    for reserve in reserves:
        result = check_reserve_address(
            db=db, reserve_address_id=reserve["id"], address=reserve["address"],
            chain=reserve["chain"], api_key=api_key,
        )
        if result.get("status") != "ok":
            errors.append(f"{reserve['exchange_name']} ({reserve['address']}): {result.get('message')}")
            continue

        checked += 1
        change_pct = result.get("change_pct")
        if change_pct is not None and change_pct <= outflow_alert_threshold_pct:
            alerts.append({
                "exchange_name": reserve["exchange_name"],
                "address": reserve["address"],
                "change_pct": change_pct,
                "balance_native": result["balance_native"],
                "previous_balance_native": result["previous_balance_native"],
            })

    return {"status": "ok", "checked": checked, "alerts": alerts, "errors": errors}