"""
modules/crypto/crypto_wallet_discovery_engine.py

Sprint CR-1: Autonomous Wallet Intelligence -- the "find suspicious
wallets automatically" mechanism.

True blockchain-wide scanning from scratch isn't realistic on free/
affordable infrastructure. The real, standard AML technique used here
instead is indirect-exposure screening: pull recent transactions
to/from addresses ALREADY known to be bad (sanctioned, or flagged by
GoPlus), and surface their counterparties -- wallets the system has
never seen before that are now flagged for having transacted with a
known bad actor. This is genuine automatic discovery of new wallets,
not just re-checking a fixed list, and it's exactly the "N-hop
exposure" concept real sanctions-screening tools use.

Uses Etherscan's V2 API (confirmed the V1 API was deprecated
2025-08-15; this targets the current, non-deprecated endpoint shape:
https://api.etherscan.io/v2/api?chainid=...&module=account&action=txlist).
The exact response schema (status/message/result array with
blockNumber/timeStamp/hash/from/to/value fields) is confirmed from
Etherscan's own current documentation.

NOTE: api.etherscan.io is outside this sandbox's allowed fetch
domains, so the live fetch itself cannot be executed or verified from
here, same caveat as the OFAC and GoPlus fetches. The counterparty-
extraction and flagging logic below is independently correct and
tested against a realistic, schema-accurate sample.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

ETHERSCAN_V2_BASE_URL = "https://api.etherscan.io/v2/api"

# chain -> Etherscan V2 chainid, confirmed from their docs (the V2 API
# is multi-chain, unified under one base URL with a chainid param,
# replacing the old per-chain-explorer V1 APIs).
ETHERSCAN_CHAIN_IDS = {
    "ethereum": 1,
    "bsc": 56,
    "polygon": 137,
    "arbitrum": 42161,
    "optimism": 10,
    "base": 8453,
    "avalanche": 43114,
}


def fetch_recent_transactions(
    address: str, chain: str, api_key: str, *, limit: int = 25, sort: str = "desc",
) -> Dict[str, Any]:
    """
    Real network call to Etherscan's V2 API -- cannot be executed or
    verified end-to-end from this sandbox. Response parsing below
    matches Etherscan's own confirmed, current schema exactly.

    sort="desc" (default, newest first) is what the discovery engine
    uses for "recent activity". sort="asc" with limit=1 -- used by
    crypto_fraud_clustering_engine.py's common-funding-source
    method -- returns the address's very FIRST transaction instead,
    which is a different, deliberate query, not a variation of the
    same one.
    """
    chain_id = ETHERSCAN_CHAIN_IDS.get(chain.lower())
    if chain_id is None:
        return {"status": "error", "message": f"Unsupported chain: {chain}"}

    try:
        import urllib.request
        import urllib.parse

        params = urllib.parse.urlencode({
            "chainid": chain_id,
            "module": "account",
            "action": "txlist",
            "address": address,
            "page": 1,
            "offset": limit,
            "sort": sort,
            "apikey": api_key,
        })
        url = f"{ETHERSCAN_V2_BASE_URL}?{params}"

        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; WalletIntelligence/1.0)"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read())

        if str(payload.get("status")) != "1":
            # Etherscan returns status "0" with message "No transactions
            # found" for a genuinely empty, valid address -- not an
            # error condition, so surface it as an empty result rather
            # than a failure.
            message = payload.get("message", "")
            if "no transactions found" in message.lower():
                return {"status": "ok", "transactions": []}
            return {"status": "error", "message": message}

        return {"status": "ok", "transactions": payload.get("result") or []}

    except Exception as exc:
        logger.warning("Etherscan txlist fetch failed for %s: %s", address, exc)
        return {"status": "error", "message": str(exc)}


def extract_new_counterparties(
    transactions: List[Dict[str, Any]], known_bad_address: str, already_flagged: set,
) -> List[Dict[str, Any]]:
    """
    Pure, network-free extraction logic -- independently testable.
    For each transaction, identifies whichever side isn't the known-
    bad address itself, and returns it as a discovery candidate,
    skipping anything already flagged (no point re-discovering the
    same wallet) and skipping the zero address / empty strings (seen
    on contract-creation transactions, not a real counterparty).
    """
    known_bad_lower = known_bad_address.lower()
    zero_address = "0x0000000000000000000000000000000000000000"

    candidates: Dict[str, Dict[str, Any]] = {}
    for tx in transactions:
        from_addr = (tx.get("from") or "").lower()
        to_addr = (tx.get("to") or "").lower()

        counterparty = to_addr if from_addr == known_bad_lower else from_addr
        if not counterparty or counterparty in (known_bad_lower, zero_address):
            continue
        if counterparty in already_flagged:
            continue
        if counterparty in candidates:
            continue

        candidates[counterparty] = {
            "address": counterparty,
            "discovered_via_address": known_bad_address,
            "discovered_via_tx": tx.get("hash"),
            "tx_value": tx.get("value"),
            "tx_timestamp": tx.get("timeStamp"),
        }

    return list(candidates.values())


def run_discovery_cycle(
    *, db, tenant_id: Optional[str], chain: str, api_key: str, max_known_bad_to_scan: int = 10,
) -> Dict[str, Any]:
    """
    One discovery pass: pulls a batch of already-known-bad addresses
    (sanctioned addresses from the local OFAC cache, plus anything
    already flagged for mixer/scam exposure), fetches their recent
    transactions, and flags any new counterparty found.

    Deliberately scans a bounded batch (max_known_bad_to_scan) per
    call rather than the entire sanctions list at once -- Etherscan's
    free tier has real rate limits, and a single call site scanning
    thousands of sanctioned addresses in one pass would either exceed
    them or take an impractically long time; this is meant to be
    called repeatedly (e.g. on a schedule), covering more of the
    known-bad list over successive runs rather than all at once.
    """
    from modules.crypto.crypto_wallet_intelligence_repository import get_crypto_wallet_intelligence_repository

    repo = get_crypto_wallet_intelligence_repository(db=db)

    seeds: List[Dict[str, Any]] = []
    for flag in repo.list_flags(tenant_id=tenant_id, limit=max_known_bad_to_scan):
        seeds.append({"address": flag["address"], "reason_type": flag["exposure_type"]})

    if not seeds:
        return {"status": "ok", "seeds_scanned": 0, "new_wallets_flagged": 0}

    already_flagged = {f["address"].lower() for f in repo.list_flags(tenant_id=tenant_id, limit=10000)}

    new_flags_count = 0
    errors: List[str] = []

    for seed in seeds:
        tx_result = fetch_recent_transactions(seed["address"], chain, api_key)
        if tx_result.get("status") != "ok":
            errors.append(f"{seed['address']}: {tx_result.get('message')}")
            continue

        candidates = extract_new_counterparties(
            tx_result["transactions"], seed["address"], already_flagged,
        )

        for candidate in candidates:
            repo.add_flag(
                tenant_id=tenant_id,
                address=candidate["address"],
                chain=chain,
                exposure_type=seed["reason_type"],
                severity="MEDIUM",
                source="INDIRECT_EXPOSURE",
                evidence={
                    "reason": f"Transacted with known {seed['reason_type'].lower()}-exposed address",
                    "tx_hash": candidate["discovered_via_tx"],
                },
                discovered_via_address=candidate["discovered_via_address"],
                discovered_via_tx=candidate["discovered_via_tx"],
            )
            already_flagged.add(candidate["address"].lower())
            new_flags_count += 1

    return {
        "status": "ok",
        "seeds_scanned": len(seeds),
        "new_wallets_flagged": new_flags_count,
        "errors": errors,
    }