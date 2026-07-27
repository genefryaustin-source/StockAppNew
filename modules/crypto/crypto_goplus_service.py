"""
modules/crypto/crypto_goplus_service.py

Sprint CR-1: Autonomous Wallet Intelligence -- free-tier scam/mixer/
rug-pull data source.

Wraps two real, documented, license-free GoPlus Security endpoints:

  Malicious Address API:
    GET https://api.gopluslabs.io/api/v1/address_security/{address}?chain_id={chain_id}
    Confirmed exact response fields from the official docs
    (docs.gopluslabs.io/reference/response-details-1): mixer,
    sanctioned, phishing_activities, blackmail_activities,
    stealing_attack, fake_kyc, malicious_mining_activities,
    darkweb_transactions, cybercrime, money_laundering,
    financial_crime, blacklist_doubt, honeypot_related_address,
    fake_token, fake_standard_interface, gas_abuse -- each a string
    "1"/"0", not a real boolean.

  Rug-Pull Detection API (Beta), contract/DeFi-protocol addresses
  only, not plain wallets:
    GET https://api.gopluslabs.io/api/v1/rugpull_detecting/{chain_id}?contract_addresses={address}
    Confirmed exact response fields
    (docs.gopluslabs.io/reference/response-details-7):
    privilege_withdraw, withdraw_missing, blacklist, selfdestruct,
    approval_abuse -- each "1"/"0"/"-1" ("-1" = unknown, a real third
    state, not just true/false).

NOTE: both endpoints' exact response *envelope* (whether fields sit
directly at the top level, or nested under a "result" key -- GoPlus's
other APIs, e.g. Token Security, key results by the queried address)
could not be confirmed with a live call from this sandbox
(api.gopluslabs.io is outside the allowed fetch domains here).
_unwrap_result() below handles the reasonable shapes defensively; the
exact envelope needs a live call to fully confirm in the deployed
environment, same caveat as the OFAC fetch itself.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

GOPLUS_BASE_URL = "https://api.gopluslabs.io/api/v1"

# Chain name -> GoPlus chain_id, confirmed against the docs' listed
# enum values for the Malicious Address API's chain_id query param.
CHAIN_IDS = {
    "ethereum": "1",
    "bsc": "56",
    "polygon": "137",
    "arbitrum": "42161",
    "optimism": "10",
    "avalanche": "43114",
    "fantom": "250",
    "base": "8453",
    "tron": "tron",
    "solana": "solana",
}

# Malicious Address API fields -> which exposure_type each maps to.
# "sanctioned" and "mixer" map directly and unambiguously. Everything
# else GoPlus flags is grouped under SCAM -- these are all forms of
# fraud/theft/financial-crime activity, not sanctions or mixing
# specifically, and splitting them further than the source data
# itself distinguishes would be inventing precision that isn't there.
_SANCTION_FIELDS = ["sanctioned"]
_MIXER_FIELDS = ["mixer"]
_SCAM_FIELDS = [
    "phishing_activities", "blackmail_activities", "stealing_attack", "fake_kyc",
    "malicious_mining_activities", "darkweb_transactions", "cybercrime",
    "money_laundering", "financial_crime", "blacklist_doubt",
    "honeypot_related_address", "fake_token", "fake_standard_interface", "gas_abuse",
]


def _unwrap_result(payload: Dict[str, Any], address: Optional[str] = None) -> Dict[str, Any]:
    """
    Defensively finds the actual data dict within a GoPlus response,
    handling the reasonable shapes an address-keyed vs. flat response
    could take -- see the module docstring for why this can't be
    pinned down more precisely without a live call.
    """
    if not isinstance(payload, dict):
        return {}
    if "result" in payload and isinstance(payload["result"], dict):
        result = payload["result"]
        if address and address.lower() in result and isinstance(result[address.lower()], dict):
            return result[address.lower()]
        return result
    return payload


def parse_address_security_response(payload: Dict[str, Any], address: Optional[str] = None) -> Dict[str, Any]:
    """
    Parses a Malicious Address API response into exposure flags.
    Pure parsing, independently testable against a hand-built sample
    matching the confirmed field names -- no network dependency.
    """
    data = _unwrap_result(payload, address)

    def _is_true(field: str) -> bool:
        return str(data.get(field, "0")) == "1"

    sanction_hits = [f for f in _SANCTION_FIELDS if _is_true(f)]
    mixer_hits = [f for f in _MIXER_FIELDS if _is_true(f)]
    scam_hits = [f for f in _SCAM_FIELDS if _is_true(f)]

    return {
        "sanction": bool(sanction_hits),
        "mixer": bool(mixer_hits),
        "scam": bool(scam_hits),
        "scam_reasons": scam_hits,
        "data_source": data.get("data_source"),
        "raw": data,
    }


def parse_rugpull_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parses a Rug-Pull Detection API response into a risk summary.
    "-1" (unknown) is deliberately NOT treated as a risk hit -- it
    means GoPlus couldn't determine the flag, not that the flag is
    true. Conflating "unknown" with "risky" would overstate confidence
    the data doesn't actually have.
    """
    data = _unwrap_result(payload)

    def _flag(field: str) -> Optional[bool]:
        val = str(data.get(field, "-1"))
        if val == "1":
            return True
        if val == "0":
            return False
        return None  # unknown

    flags = {
        "privilege_withdraw": _flag("privilege_withdraw"),
        "withdraw_missing": _flag("withdraw_missing"),
        "blacklist_function": _flag("blacklist"),
        "selfdestruct": _flag("selfdestruct"),
        "approval_abuse": _flag("approval_abuse"),
    }
    risk_hits = [k for k, v in flags.items() if v is True]

    return {
        "rug_pull_risk": bool(risk_hits),
        "risk_reasons": risk_hits,
        "flags": flags,
        "contract_name": data.get("contract_name"),
        "is_open_source": str(data.get("is_open_source")) == "1",
        "raw": data,
    }


def check_address_security(address: str, chain: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Real network call to GoPlus -- cannot be executed or verified
    end-to-end from this sandbox (api.gopluslabs.io is outside the
    allowed fetch domains here). parse_address_security_response()
    above is independently correct and unit-tested against the
    confirmed field schema; this is a thin, low-risk fetch shell
    around it, same pattern as the OFAC fetch wrapper.
    """
    chain_id = CHAIN_IDS.get(chain.lower())
    if chain_id is None:
        return {"status": "error", "message": f"Unsupported chain: {chain}"}

    try:
        import urllib.request

        url = f"{GOPLUS_BASE_URL}/address_security/{address}?chain_id={chain_id}"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; WalletIntelligence/1.0)"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read())

        parsed = parse_address_security_response(payload, address)
        return {"status": "ok", **parsed}

    except Exception as exc:
        logger.warning("GoPlus address_security check failed for %s: %s", address, exc)
        return {"status": "error", "message": str(exc)}


def check_rugpull_risk(contract_address: str, chain: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Real network call to GoPlus's rug-pull endpoint -- same sandbox
    limitation as check_address_security() above.
    """
    chain_id = CHAIN_IDS.get(chain.lower())
    if chain_id is None:
        return {"status": "error", "message": f"Unsupported chain: {chain}"}

    try:
        import urllib.request

        url = f"{GOPLUS_BASE_URL}/rugpull_detecting/{chain_id}?contract_addresses={contract_address}"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; WalletIntelligence/1.0)"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read())

        parsed = parse_rugpull_response(payload)
        return {"status": "ok", **parsed}

    except Exception as exc:
        logger.warning("GoPlus rug-pull check failed for %s: %s", contract_address, exc)
        return {"status": "error", "message": str(exc)}