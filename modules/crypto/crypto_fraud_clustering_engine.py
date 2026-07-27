"""
modules/crypto/crypto_fraud_clustering_engine.py

Sprint CR-2: Crypto Threat Intelligence -- Fraud Clustering.

Two independent, real forensic clustering methods:

1. COMMON_FUNDING_SOURCE: for each flagged wallet, fetch its very
   FIRST transaction (sort="asc", limit=1) and identify who funded
   it. If two or more flagged wallets were funded by the exact same
   upstream address, that's a real, standard blockchain-forensics
   signal that they were set up by the same actor -- the account-
   based-chain analogue of the "common input ownership" heuristic
   used in UTXO forensics, adapted for how funding actually works on
   account-based chains like Ethereum (there's no multi-input
   transaction to exploit the way Bitcoin has; the signal here is
   "who sent the very first funds", not "which inputs were spent
   together").

2. TRANSACTION_GRAPH: groups wallets that were all discovered via the
   SAME known-bad seed address (crypto_wallet_risk_flags.
   discovered_via_address, already populated by CR-1's discovery
   engine) -- wallets that all transacted directly with the same
   known-bad actor are plausibly part of the same operation. Weaker
   evidence than common funding (transacting with the same address
   doesn't necessarily mean common ownership the way sharing a funder
   does), so clusters from this method get LOWER confidence by
   design, not the same default as funding-source clusters.

Both write into crypto_fraud_clusters / crypto_threat_entity_addresses
(crypto_threat_intelligence_repository.py), reusing
find_cluster_by_key() so re-running clustering strengthens an existing
cluster (more members added) rather than creating duplicate clusters
for the same funding source or seed address.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def get_first_funding_source(address: str, chain: str, api_key: str) -> Dict[str, Any]:
    """
    Fetches an address's very first transaction and identifies its
    funding source (whoever sent it, if it was the receiving side of
    that first transaction -- if the address's first-ever transaction
    was itself an outgoing send, it wasn't "funded" by that
    transaction, so funding_source is None rather than guessing).
    """
    from modules.crypto.crypto_wallet_discovery_engine import fetch_recent_transactions

    result = fetch_recent_transactions(address, chain, api_key, limit=1, sort="asc")
    if result.get("status") != "ok":
        return {"status": "error", "message": result.get("message")}

    transactions = result.get("transactions") or []
    if not transactions:
        return {"status": "ok", "funding_source": None, "first_tx": None}

    first_tx = transactions[0]
    to_addr = (first_tx.get("to") or "").lower()
    from_addr = (first_tx.get("from") or "").lower()

    funding_source = from_addr if to_addr == address.lower() else None

    return {"status": "ok", "funding_source": funding_source, "first_tx": first_tx}


def build_funding_source_clusters(
    *, db, tenant_id: Optional[str], addresses: List[str], chain: str, api_key: str,
) -> Dict[str, Any]:
    """
    For a batch of flagged addresses, looks up each one's funding
    source and groups any that share the same one into a cluster.
    Addresses with no identifiable funding source (contract-created
    wallets, addresses whose first activity was outgoing, or lookup
    failures) are simply excluded from clustering, not treated as
    their own singleton clusters -- a cluster of one isn't a cluster.
    """
    from modules.crypto.crypto_threat_intelligence_repository import get_crypto_threat_intelligence_repository

    repo = get_crypto_threat_intelligence_repository(db=db)

    funding_map: Dict[str, List[str]] = {}
    errors: List[str] = []

    for address in addresses:
        result = get_first_funding_source(address, chain, api_key)
        if result.get("status") != "ok":
            errors.append(f"{address}: {result.get('message')}")
            continue

        funding_source = result.get("funding_source")
        if not funding_source:
            continue

        funding_map.setdefault(funding_source, []).append(address)

    clusters_created = 0
    clusters_strengthened = 0
    members_linked = 0

    for funding_source, member_addresses in funding_map.items():
        if len(member_addresses) < 2:
            continue  # a cluster of one address isn't a cluster

        existing = repo.find_cluster_by_key(
            tenant_id=tenant_id, cluster_method="COMMON_FUNDING_SOURCE", cluster_key=funding_source,
        )
        if existing:
            cluster_id = existing["id"]
            clusters_strengthened += 1
        else:
            cluster_id = repo.create_cluster(
                tenant_id=tenant_id, cluster_method="COMMON_FUNDING_SOURCE",
                cluster_key=funding_source, confidence="HIGH",
            )
            clusters_created += 1

        for address in member_addresses:
            repo.link_address(
                entity_type="CLUSTER", entity_id=cluster_id, address=address, chain=chain,
                role="MEMBER", evidence={"funding_source": funding_source},
            )
            members_linked += 1

    return {
        "status": "ok",
        "addresses_checked": len(addresses),
        "clusters_created": clusters_created,
        "clusters_strengthened": clusters_strengthened,
        "members_linked": members_linked,
        "errors": errors,
    }


def build_transaction_graph_clusters(*, db, tenant_id: Optional[str]) -> Dict[str, Any]:
    """
    Groups already-flagged wallets by shared discovered_via_address
    (populated by CR-1's discovery engine when it found a new wallet
    by watching a known-bad seed's transactions) -- no network calls
    needed, this is a pure grouping of data already on hand.

    Deliberately LOWER confidence than funding-source clusters: two
    wallets that both happened to transact with the same known-bad
    address is real but weaker evidence of common ownership than two
    wallets that were funded by the exact same source.
    """
    from modules.crypto.crypto_wallet_intelligence_repository import get_crypto_wallet_intelligence_repository
    from modules.crypto.crypto_threat_intelligence_repository import get_crypto_threat_intelligence_repository

    wallet_repo = get_crypto_wallet_intelligence_repository(db=db)
    threat_repo = get_crypto_threat_intelligence_repository(db=db)

    flags = wallet_repo.list_flags(tenant_id=tenant_id, limit=10000)

    seed_groups: Dict[str, List[Dict[str, Any]]] = {}
    for flag in flags:
        seed = flag.get("discovered_via_address")
        if not seed:
            continue
        seed_groups.setdefault(seed, []).append(flag)

    clusters_created = 0
    clusters_strengthened = 0
    members_linked = 0

    for seed_address, members in seed_groups.items():
        if len(members) < 2:
            continue

        existing = threat_repo.find_cluster_by_key(
            tenant_id=tenant_id, cluster_method="TRANSACTION_GRAPH", cluster_key=seed_address,
        )
        if existing:
            cluster_id = existing["id"]
            clusters_strengthened += 1
        else:
            cluster_id = threat_repo.create_cluster(
                tenant_id=tenant_id, cluster_method="TRANSACTION_GRAPH",
                cluster_key=seed_address, confidence="MEDIUM",
            )
            clusters_created += 1

        for member in members:
            threat_repo.link_address(
                entity_type="CLUSTER", entity_id=cluster_id, address=member["address"],
                chain=member["chain"], role="MEMBER",
                evidence={"shared_seed_address": seed_address},
            )
            members_linked += 1

    return {
        "status": "ok",
        "seed_groups_examined": len(seed_groups),
        "clusters_created": clusters_created,
        "clusters_strengthened": clusters_strengthened,
        "members_linked": members_linked,
    }