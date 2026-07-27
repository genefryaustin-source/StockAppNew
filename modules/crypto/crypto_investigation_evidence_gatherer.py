"""
modules/crypto/crypto_investigation_evidence_gatherer.py

Sprint CR-5: Autonomous Investigation Engine -- evidence gathering.

Pulls together everything already built in CR-1 and CR-2 for a given
address, into one evidence snapshot: sanction/mixer/scam exposure
(CR-1's provider abstraction), any existing risk flags and how the
address was discovered (CR-1's repository), and any threat actor/
campaign/fraud-cluster associations (CR-2's repository). This is pure
data gathering -- no AI involved yet; crypto_investigation_ai_engine.py
takes this snapshot and produces the narrative/recommendation.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def gather_evidence(*, db, address: str, chain: str, tenant_id: Optional[str]) -> Dict[str, Any]:
    from modules.crypto.crypto_wallet_intelligence_provider import get_wallet_risk_assessment
    from modules.crypto.crypto_wallet_intelligence_repository import get_crypto_wallet_intelligence_repository
    from modules.crypto.crypto_threat_intelligence_repository import get_crypto_threat_intelligence_repository

    risk_assessment = get_wallet_risk_assessment(address, chain, db=db, tenant_id=tenant_id)

    wallet_repo = get_crypto_wallet_intelligence_repository(db=db)
    existing_flags = [
        f for f in wallet_repo.list_flags(tenant_id=tenant_id, limit=10000)
        if f["address"] == address.lower()
    ]

    threat_repo = get_crypto_threat_intelligence_repository(db=db)
    entity_links = threat_repo.list_entities_for_address(address)

    # Resolve entity links into readable names/context, not just raw
    # entity_type/entity_id pairs -- an investigation report should
    # say "linked to threat actor 'Fake Exchange Ring #7'", not
    # "linked to ACTOR 1".
    resolved_entities = []
    for link in entity_links:
        entity_type = link.get("entity_type")
        entity_id = link.get("entity_id")

        if entity_type == "ACTOR":
            actors = threat_repo.list_actors(tenant_id=tenant_id)
            match = next((a for a in actors if a["id"] == entity_id), None)
            if match:
                resolved_entities.append({
                    "type": "Threat Actor", "name": match["name"], "actor_type": match.get("actor_type"),
                })
        elif entity_type == "CAMPAIGN":
            campaigns = threat_repo.list_campaigns(tenant_id=tenant_id)
            match = next((c for c in campaigns if c["id"] == entity_id), None)
            if match:
                resolved_entities.append({
                    "type": "Scam Campaign", "name": match["name"], "status": match.get("status"),
                })
        elif entity_type == "CLUSTER":
            clusters = threat_repo.list_clusters(tenant_id=tenant_id)
            match = next((c for c in clusters if c["id"] == entity_id), None)
            if match:
                resolved_entities.append({
                    "type": "Fraud Cluster", "method": match.get("cluster_method"),
                    "confidence": match.get("confidence"), "member_count": match.get("member_count"),
                })

    return {
        "address": address,
        "chain": chain,
        "risk_assessment": risk_assessment,
        "existing_flags": [
            {
                "exposure_type": f["exposure_type"], "severity": f["severity"], "source": f["source"],
                "discovered_via_address": f.get("discovered_via_address"),
            }
            for f in existing_flags
        ],
        "entity_associations": resolved_entities,
    }