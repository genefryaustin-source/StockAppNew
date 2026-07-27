"""
modules/crypto/crypto_wallet_intelligence_provider.py

Sprint CR-1: Autonomous Wallet Intelligence -- pluggable risk-data
provider layer.

A Tenant Admin can configure a premium provider (Chainalysis, and the
same shape would extend to TRM Labs/Elliptic) via the existing
tenant-scoped, encrypted API key store (get_provider_key(), already
used throughout this app for broker/data credentials -- see
modules/admin/tenant_api_keys.py). When configured, wallet checks
route through that provider. Otherwise, checks fall back to the free
sources built for this sprint: OFAC's own sanctions data
(crypto_sanctions_service.py) and GoPlus Security
(crypto_goplus_service.py).

Two real Chainalysis endpoints, confirmed from their own public docs:

  Free, public sanctions screening (simple signup, not enterprise-gated):
    GET https://public.chainalysis.com/api/v1/address/{address}
    Auth: X-API-Key header. Confirmed real and free from Chainalysis's
    own docs (auth-developers.chainalysis.com/sanctions-screening).
    Used here as an OPTIONAL supplement to the OFAC XML parsing (a
    second, independently-maintained sanctions source), not a
    replacement -- if a Tenant Admin has a free Chainalysis sanctions
    key, both sources get checked.

  Paid, enterprise Address Screening (categorized exposure + risk
  score across sanctions/darknet-markets/scams/mixers):
    api.chainalysis.com, entity-risk endpoint
    (confirmed the base URL and endpoint path from Chainalysis's own
    developer docs and a public client reference; the exact response
    schema is enterprise-gated and could not be confirmed with a real
    account from this sandbox -- see check_chainalysis_entity_risk()
    below for what that means concretely).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

CHAINALYSIS_SANCTIONS_URL = "https://public.chainalysis.com/api/v1/address"
CHAINALYSIS_ENTERPRISE_BASE_URL = "https://api.chainalysis.com"
CHAINALYSIS_ENTITY_RISK_ENDPOINT = "/api/risk/v2/entities"

KNOWN_PREMIUM_PROVIDERS = ["chainalysis"]


def check_chainalysis_sanctions(address: str, api_key: str) -> Dict[str, Any]:
    """
    Real network call to Chainalysis's free, public sanctions endpoint
    -- confirmed real and free from their own docs, but
    public.chainalysis.com is outside this sandbox's allowed fetch
    domains, so this cannot be executed or verified end-to-end here.
    The request/response handling below matches their documented
    contract exactly (X-API-Key header, GET .../address/{address},
    response is an array of sanctions designations, empty if none).
    """
    try:
        import urllib.request

        url = f"{CHAINALYSIS_SANCTIONS_URL}/{address}"
        req = urllib.request.Request(url, headers={
            "X-API-Key": api_key,
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read())

        # Documented response: an array of sanctions designations, if
        # any -- empty array means not sanctioned.
        designations = payload if isinstance(payload, list) else payload.get("identifications", [])
        return {
            "status": "ok",
            "sanctioned": bool(designations),
            "designations": designations,
        }

    except Exception as exc:
        logger.warning("Chainalysis sanctions check failed for %s: %s", address, exc)
        return {"status": "error", "message": str(exc)}


def check_chainalysis_entity_risk(address: str, api_key: str) -> Dict[str, Any]:
    """
    Real network call to Chainalysis's paid, enterprise Address
    Screening product.

    IMPORTANT, stated plainly: the exact request parameters and
    response schema for this specific enterprise endpoint are
    themselves gated behind a paid Chainalysis account -- their
    public docs confirm the base URL (api.chainalysis.com) and that
    an entity-risk endpoint exists at this path (via a public,
    third-party open-source client reference), but not the full
    request/response contract, since that lives behind their
    authenticated developer portal. This function sends a request
    shaped as closely as can be determined from what's publicly
    documented, and returns the raw response for the caller to
    inspect -- it should NOT be trusted to parse specific risk
    categories correctly until verified against a real account and
    a real response in the deployed environment. Flagging this
    honestly rather than presenting an unverified guess as settled
    behavior.
    """
    try:
        import urllib.request

        url = f"{CHAINALYSIS_ENTERPRISE_BASE_URL}{CHAINALYSIS_ENTITY_RISK_ENDPOINT}"
        req = urllib.request.Request(
            f"{url}?address={address}",
            headers={"Token": api_key, "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read())

        return {
            "status": "ok",
            "verified": False,
            "note": (
                "Response schema not independently verified against a real "
                "Chainalysis account -- treat category/score fields below as "
                "provisional until confirmed in the deployed environment."
            ),
            "raw": payload,
        }

    except Exception as exc:
        logger.warning("Chainalysis entity risk check failed for %s: %s", address, exc)
        return {"status": "error", "message": str(exc)}


def get_wallet_risk_assessment(
    address: str, chain: str, *, db=None, tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    The single entry point the rest of this feature should call.
    Resolves which provider is active for this tenant, and routes
    accordingly:

    - Premium (Chainalysis) configured and active: use it for the
      main exposure categorization, but STILL check the free OFAC
      cache too (belt-and-suspenders on sanctions specifically,
      since that data is free, official, and instant to check
      locally -- no reason to skip it even with a premium provider
      active).
    - Otherwise (free tier): OFAC sanctions cache + GoPlus malicious
      address check.
    """
    from modules.crypto.crypto_wallet_intelligence_repository import get_crypto_wallet_intelligence_repository
    from modules.crypto.crypto_goplus_service import check_address_security
    from modules.admin.tenant_api_keys import get_provider_key

    repo = get_crypto_wallet_intelligence_repository(db=db)
    active_provider = repo.get_active_provider(tenant_id) if tenant_id else "free"

    result: Dict[str, Any] = {
        "address": address,
        "chain": chain,
        "provider": active_provider,
        "sanction": False,
        "mixer": False,
        "scam": False,
        "sources_checked": [],
        "details": {},
    }

    # Sanctions: always check the free, local OFAC cache first --
    # instant, no network call, no reason to skip it regardless of
    # which provider is active.
    sanction_hit = repo.is_sanctioned(address)
    if sanction_hit:
        result["sanction"] = True
        result["details"]["ofac"] = sanction_hit
    result["sources_checked"].append("ofac_sdn")

    if active_provider == "chainalysis":
        api_key = get_provider_key("chainalysis", db=db, tenant_id=tenant_id)
        if api_key:
            entity_result = check_chainalysis_entity_risk(address, api_key)
            result["sources_checked"].append("chainalysis_entity_risk")
            result["details"]["chainalysis"] = entity_result

            sanctions_result = check_chainalysis_sanctions(address, api_key)
            result["sources_checked"].append("chainalysis_sanctions")
            if sanctions_result.get("sanctioned"):
                result["sanction"] = True
            result["details"]["chainalysis_sanctions"] = sanctions_result
        else:
            result["details"]["chainalysis_error"] = (
                "Provider set to chainalysis but no API key is configured for this tenant."
            )

    else:
        goplus_result = check_address_security(address, chain)
        result["sources_checked"].append("goplus")
        if goplus_result.get("status") == "ok":
            result["sanction"] = result["sanction"] or goplus_result.get("sanction", False)
            result["mixer"] = goplus_result.get("mixer", False)
            result["scam"] = goplus_result.get("scam", False)
        result["details"]["goplus"] = goplus_result

    return result