"""
modules/crypto/crypto_threat_intelligence_ui.py

Sprint CR-2: Crypto Threat Intelligence -- UI layer.

Threat Actor Profiles and Scam Campaign Tracking are primarily
analyst-entered (a human names and describes a known scammer or
campaign; automated discovery alone can't reliably invent a name or
narrative), with addresses either linked manually or pulled in from
Fraud Clustering results. Fraud Clusters are the automated piece --
run either clustering method and browse what came out.
"""

from __future__ import annotations

import streamlit as st

CHAIN_OPTIONS = ["ethereum", "bsc", "polygon", "arbitrum", "optimism", "base", "avalanche"]
ACTOR_TYPES = ["SCAMMER", "RANSOMWARE_GROUP", "PHISHING_OPERATOR", "MIXER_OPERATOR", "FAKE_EXCHANGE", "OTHER"]
CAMPAIGN_TYPES = ["PHISHING", "RUG_PULL", "FAKE_EXCHANGE", "ROMANCE_SCAM", "PONZI", "OTHER"]
CAMPAIGN_STATUSES = ["ACTIVE", "DORMANT", "TAKEN_DOWN"]


def _get_repo(db):
    from modules.crypto.crypto_threat_intelligence_repository import get_crypto_threat_intelligence_repository
    return get_crypto_threat_intelligence_repository(db=db)


# ======================================================================
# Threat Actors
# ======================================================================

def render_threat_actors(db, tenant_id: str) -> None:
    st.markdown("**Threat Actor Profiles**")
    st.caption(
        "A persistent identity (a named/aliased scammer, ransomware group, "
        "etc.) that can own multiple wallet addresses over time."
    )

    repo = _get_repo(db)

    with st.expander("➕ New actor profile"):
        name = st.text_input("Name", key="ti_actor_name")
        actor_type = st.selectbox("Actor type", ACTOR_TYPES, key="ti_actor_type")
        aliases_raw = st.text_input("Aliases (comma-separated)", key="ti_actor_aliases")
        description = st.text_area("Description", key="ti_actor_description")

        if st.button("Create actor", key="ti_create_actor_btn"):
            if not name.strip():
                st.warning("Enter a name first.")
            else:
                aliases = [a.strip() for a in aliases_raw.split(",") if a.strip()]
                actor_id = repo.create_actor(
                    tenant_id=tenant_id, name=name.strip(), actor_type=actor_type,
                    aliases=aliases, description=description.strip() or None,
                )
                st.success(f"Actor created: {name} (ID {actor_id})")

    st.divider()
    actors = repo.list_actors(tenant_id=tenant_id)
    if not actors:
        st.info("No threat actor profiles yet. Create one above.")
        return

    for actor in actors:
        with st.expander(f"🎭 {actor['name']} ({actor['actor_type']})"):
            if actor.get("aliases"):
                st.caption(f"Aliases: {', '.join(actor['aliases'])}")
            if actor.get("description"):
                st.write(actor["description"])
            st.caption(f"Confidence: {actor['confidence']} · Last activity: {actor.get('last_activity_at')}")

            addresses = repo.list_addresses_for_entity("ACTOR", actor["id"])
            if addresses:
                st.markdown("**Linked addresses**")
                st.dataframe(
                    [{"Address": a["address"], "Chain": a["chain"], "Role": a.get("role") or "-"} for a in addresses],
                    use_container_width=True, hide_index=True,
                )
            else:
                st.caption("No addresses linked yet.")

            link_cols = st.columns([3, 1, 1])
            with link_cols[0]:
                new_addr = st.text_input("Link an address", key=f"ti_actor_link_addr_{actor['id']}")
            with link_cols[1]:
                new_chain = st.selectbox("Chain", CHAIN_OPTIONS, key=f"ti_actor_link_chain_{actor['id']}")
            with link_cols[2]:
                st.write("")
                if st.button("Link", key=f"ti_actor_link_btn_{actor['id']}"):
                    if new_addr.strip():
                        repo.link_address(
                            entity_type="ACTOR", entity_id=actor["id"], address=new_addr.strip(),
                            chain=new_chain, role="MANUAL",
                        )
                        repo.touch_actor_activity(actor["id"])
                        st.success(f"Linked {new_addr} to {actor['name']}.")
                    else:
                        st.warning("Enter an address first.")


# ======================================================================
# Scam Campaigns
# ======================================================================

def render_scam_campaigns(db, tenant_id: str) -> None:
    st.markdown("**Scam Campaign Tracking**")
    st.caption(
        "A bounded operation (a specific phishing site, a specific rug-pull "
        "token, a specific fake-exchange scheme), optionally attributed to a "
        "threat actor."
    )

    repo = _get_repo(db)
    actors = repo.list_actors(tenant_id=tenant_id)
    actor_options = {"(none)": None, **{f"{a['name']} (ID {a['id']})": a["id"] for a in actors}}

    with st.expander("➕ New campaign"):
        name = st.text_input("Campaign name", key="ti_campaign_name")
        campaign_type = st.selectbox("Campaign type", CAMPAIGN_TYPES, key="ti_campaign_type")
        actor_label = st.selectbox("Attributed to actor", list(actor_options.keys()), key="ti_campaign_actor")
        description = st.text_area("Description", key="ti_campaign_description")
        est_victims = st.number_input("Estimated victim count", min_value=0, value=0, key="ti_campaign_victims")
        est_loss = st.number_input("Estimated loss (USD)", min_value=0.0, value=0.0, key="ti_campaign_loss")

        if st.button("Create campaign", key="ti_create_campaign_btn"):
            if not name.strip():
                st.warning("Enter a campaign name first.")
            else:
                campaign_id = repo.create_campaign(
                    tenant_id=tenant_id, name=name.strip(), campaign_type=campaign_type,
                    actor_id=actor_options[actor_label], description=description.strip() or None,
                )
                st.success(f"Campaign created: {name} (ID {campaign_id})")

    st.divider()
    campaigns = repo.list_campaigns(tenant_id=tenant_id)
    if not campaigns:
        st.info("No scam campaigns tracked yet. Create one above.")
        return

    actor_names_by_id = {a["id"]: a["name"] for a in actors}

    for campaign in campaigns:
        status_icon = {"ACTIVE": "🔴", "DORMANT": "🟡", "TAKEN_DOWN": "✅"}.get(campaign["status"], "⚪")
        with st.expander(f"{status_icon} {campaign['name']} ({campaign['campaign_type']}) -- {campaign['status']}"):
            if campaign.get("actor_id"):
                st.caption(f"Attributed to: {actor_names_by_id.get(campaign['actor_id'], 'Unknown actor')}")
            if campaign.get("description"):
                st.write(campaign["description"])
            if campaign.get("estimated_victim_count") or campaign.get("estimated_loss_usd"):
                st.caption(
                    f"Estimated victims: {campaign.get('estimated_victim_count') or 0} · "
                    f"Estimated loss: ${campaign.get('estimated_loss_usd') or 0:,.2f}"
                )

            addresses = repo.list_addresses_for_entity("CAMPAIGN", campaign["id"])
            if addresses:
                st.markdown("**Linked addresses**")
                st.dataframe(
                    [{"Address": a["address"], "Chain": a["chain"], "Role": a.get("role") or "-"} for a in addresses],
                    use_container_width=True, hide_index=True,
                )
            else:
                st.caption("No addresses linked yet.")

            link_cols = st.columns([3, 1, 1])
            with link_cols[0]:
                new_addr = st.text_input("Link an address", key=f"ti_campaign_link_addr_{campaign['id']}")
            with link_cols[1]:
                new_chain = st.selectbox("Chain", CHAIN_OPTIONS, key=f"ti_campaign_link_chain_{campaign['id']}")
            with link_cols[2]:
                st.write("")
                if st.button("Link", key=f"ti_campaign_link_btn_{campaign['id']}"):
                    if new_addr.strip():
                        repo.link_address(
                            entity_type="CAMPAIGN", entity_id=campaign["id"], address=new_addr.strip(),
                            chain=new_chain, role="MANUAL",
                        )
                        st.success(f"Linked {new_addr} to {campaign['name']}.")
                    else:
                        st.warning("Enter an address first.")

            status_cols = st.columns(len(CAMPAIGN_STATUSES))
            for i, status in enumerate(CAMPAIGN_STATUSES):
                with status_cols[i]:
                    if status != campaign["status"] and st.button(
                        f"Mark {status}", key=f"ti_campaign_status_{campaign['id']}_{status}",
                    ):
                        repo.set_campaign_status(campaign["id"], status)
                        st.success(f"Status updated to {status}.")


# ======================================================================
# Fraud Clusters
# ======================================================================

def render_fraud_clusters(db, tenant_id: str) -> None:
    st.markdown("**Fraud Clustering**")
    st.caption(
        "Groups of addresses linked by a specific, named clustering "
        "method -- addresses funded by the same upstream source (strong "
        "signal), or addresses that all transacted with the same known-bad "
        "seed address (weaker signal)."
    )

    repo = _get_repo(db)

    run_cols = st.columns(2)
    with run_cols[0]:
        st.markdown("**Common funding source** (needs Etherscan key)")
        if st.button("▶️ Run funding-source clustering", key="ti_run_funding_cluster_btn"):
            from modules.admin.tenant_api_keys import get_provider_key
            from modules.crypto.crypto_wallet_intelligence_repository import get_crypto_wallet_intelligence_repository
            from modules.crypto.crypto_fraud_clustering_engine import build_funding_source_clusters

            etherscan_key = get_provider_key("etherscan", db=db, tenant_id=tenant_id)
            if not etherscan_key:
                st.warning("No Etherscan API key configured. Add one under Admin Settings.")
            else:
                wallet_repo = get_crypto_wallet_intelligence_repository(db=db)
                addresses = [f["address"] for f in wallet_repo.list_flags(tenant_id=tenant_id, limit=200)]
                with st.spinner(f"Checking funding sources for {len(addresses)} flagged wallet(s)..."):
                    result = build_funding_source_clusters(
                        db=db, tenant_id=tenant_id, addresses=addresses, chain="ethereum", api_key=etherscan_key,
                    )
                st.success(
                    f"Checked {result['addresses_checked']} address(es): "
                    f"{result['clusters_created']} new cluster(s), "
                    f"{result['clusters_strengthened']} strengthened."
                )

    with run_cols[1]:
        st.markdown("**Transaction graph** (no network calls needed)")
        if st.button("▶️ Run transaction-graph clustering", key="ti_run_graph_cluster_btn"):
            from modules.crypto.crypto_fraud_clustering_engine import build_transaction_graph_clusters

            result = build_transaction_graph_clusters(db=db, tenant_id=tenant_id)
            st.success(
                f"Examined {result['seed_groups_examined']} seed group(s): "
                f"{result['clusters_created']} new cluster(s), "
                f"{result['clusters_strengthened']} strengthened."
            )

    st.divider()
    clusters = repo.list_clusters(tenant_id=tenant_id)
    if not clusters:
        st.info("No fraud clusters yet. Run one of the methods above.")
        return

    for cluster in clusters:
        confidence_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "⚪"}.get(cluster["confidence"], "⚪")
        with st.expander(
            f"{confidence_icon} {cluster['cluster_method']} -- {cluster['member_count']} member(s) "
            f"(confidence: {cluster['confidence']})"
        ):
            st.caption(f"Cluster key: {cluster['cluster_key']}")
            addresses = repo.list_addresses_for_entity("CLUSTER", cluster["id"])
            st.dataframe(
                [{"Address": a["address"], "Chain": a["chain"]} for a in addresses],
                use_container_width=True, hide_index=True,
            )