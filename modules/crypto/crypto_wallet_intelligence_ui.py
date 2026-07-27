"""
modules/crypto/crypto_wallet_intelligence_ui.py

Sprint CR-1: Autonomous Wallet Intelligence -- UI layer.

Ties together crypto_wallet_intelligence_repository,
crypto_wallet_intelligence_provider, and
crypto_wallet_discovery_engine into a single tab: manual wallet
lookup (the old "Investigate wallet" concept, extended with real
sanction/mixer/scam/rug-pull flags), a list of automatically
discovered suspicious wallets, a way to trigger a discovery cycle,
and a Tenant Admin panel to choose the active risk-data provider.
"""

from __future__ import annotations

import streamlit as st


CHAIN_OPTIONS = ["ethereum", "bsc", "polygon", "arbitrum", "optimism", "base", "avalanche"]


def render_wallet_intelligence(db=None, user=None) -> None:
    st.subheader("🕵️ Wallet Intelligence")
    st.caption(
        "Sanction, mixer, scam, and rug-pull exposure screening -- look up a "
        "specific wallet, or run automatic discovery to find new suspicious "
        "wallets by monitoring transactions with already-known-bad addresses."
    )

    if db is None or user is None:
        st.info("Wallet Intelligence requires a signed-in session.")
        return

    tenant_id = user.get("tenant_id")
    user_id = user.get("user_id")

    if not tenant_id:
        st.warning("No tenant context available -- Wallet Intelligence is disabled.")
        return

    from modules.crypto.crypto_wallet_intelligence_repository import get_crypto_wallet_intelligence_repository

    repo = get_crypto_wallet_intelligence_repository(db=db)
    active_provider = repo.get_active_provider(tenant_id)

    sub_tabs = st.tabs([
        "🔍 Investigate Wallet", "🤖 AI Investigation", "🚨 Discovered Wallets", "🔄 Run Discovery",
        "🎭 Threat Actors", "📢 Scam Campaigns", "🕸️ Fraud Clusters",
        "⚙️ Admin Settings",
    ])

    with sub_tabs[0]:
        _render_investigate_wallet(db, tenant_id, active_provider)
    with sub_tabs[1]:
        _render_ai_investigation(db, tenant_id, user_id)
    with sub_tabs[2]:
        _render_discovered_wallets(repo, tenant_id)
    with sub_tabs[3]:
        _render_run_discovery(db, tenant_id, active_provider)
    with sub_tabs[4]:
        from modules.crypto.crypto_threat_intelligence_ui import render_threat_actors
        render_threat_actors(db, tenant_id)
    with sub_tabs[5]:
        from modules.crypto.crypto_threat_intelligence_ui import render_scam_campaigns
        render_scam_campaigns(db, tenant_id)
    with sub_tabs[6]:
        from modules.crypto.crypto_threat_intelligence_ui import render_fraud_clusters
        render_fraud_clusters(db, tenant_id)
    with sub_tabs[7]:
        _render_admin_settings(db, repo, tenant_id, active_provider)


def _render_ai_investigation(db, tenant_id: str, user_id: str) -> None:
    st.markdown("**AI Investigation**")
    st.caption(
        "The AI gathers evidence already verified elsewhere (sanctions, "
        "malicious-address checks, threat actor/campaign/cluster "
        "associations) and writes a summary with advisory risk_level and "
        "recommended actions -- for a human analyst to review, not a "
        "final determination or an auto-executed decision."
    )

    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        address = st.text_input("Wallet address", placeholder="0x1234...abcd", key="ai_invest_address")
    with col2:
        chain = st.selectbox("Chain", CHAIN_OPTIONS, key="ai_invest_chain")
    with col3:
        st.write("")
        run_clicked = st.button("🤖 Investigate", key="ai_invest_run_btn")

    if run_clicked:
        if not address.strip():
            st.warning("Enter a wallet address first.")
        else:
            from modules.crypto.crypto_investigation_ai_engine import investigate_wallet

            with st.spinner(f"Gathering evidence and analyzing {address[:16]}..."):
                result = investigate_wallet(
                    db=db, address=address.strip(), chain=chain, tenant_id=tenant_id, requested_by=user_id,
                )

            if result["status"] == "unavailable":
                st.warning(f"⚠️ AI investigation unavailable: {result.get('message')}")
            elif result["status"] == "error":
                st.error(f"Could not complete investigation: {result.get('message')}")
            else:
                risk_colors = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "CRITICAL": "🔴"}
                st.markdown(f"### {risk_colors.get(result['risk_level'], '⚪')} Risk Level: {result['risk_level']}")
                st.write(result["summary"])
                st.caption(f"Confidence: {result['confidence_note']}")

                st.markdown("**Recommended actions (for analyst review)**")
                for action in result["recommended_actions"]:
                    st.write(f"- {action}")

    st.divider()
    st.markdown("**Past investigations**")
    from modules.crypto.crypto_ai_investigation_repository import get_crypto_ai_investigation_repository

    inv_repo = get_crypto_ai_investigation_repository(db=db)
    investigations = inv_repo.list_investigations(tenant_id=tenant_id, limit=20)
    if not investigations:
        st.info("No investigations yet.")
        return

    st.dataframe(
        [
            {
                "Address": inv["address"], "Chain": inv["chain"], "Status": inv["status"],
                "Risk Level": inv.get("risk_level") or "-", "Created": str(inv["created_at"]),
            }
            for inv in investigations
        ],
        use_container_width=True, hide_index=True,
    )


def _render_investigate_wallet(db, tenant_id: str, active_provider: str) -> None:
    st.markdown("**Investigate a single wallet**")
    st.caption(
        f"Checked against: local OFAC sanctions cache"
        + (
            " + Chainalysis (premium)" if active_provider == "chainalysis"
            else " + GoPlus Security (free)"
        )
    )

    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        address = st.text_input(
            "Wallet address", placeholder="0x1234...abcd", key="wallet_intel_lookup_address",
        )
    with col2:
        chain = st.selectbox("Chain", CHAIN_OPTIONS, key="wallet_intel_lookup_chain")
    with col3:
        st.write("")
        checked = st.button("Investigate", key="wallet_intel_lookup_btn")

    if checked:
        if not address.strip():
            st.warning("Enter a wallet address first.")
        else:
            from modules.crypto.crypto_wallet_intelligence_provider import get_wallet_risk_assessment

            with st.spinner(f"Checking {address[:16]}... on {chain}"):
                result = get_wallet_risk_assessment(address.strip(), chain, db=db, tenant_id=tenant_id)

            flags = []
            if result["sanction"]:
                flags.append("🔴 SANCTIONED")
            if result["mixer"]:
                flags.append("🟠 MIXER EXPOSURE")
            if result["scam"]:
                flags.append("🟡 SCAM INDICATORS")

            if flags:
                st.error(" · ".join(flags))
            else:
                st.success("No exposure flags found across the sources checked.")

            st.caption(f"Sources checked: {', '.join(result['sources_checked'])}")
            with st.expander("Full details"):
                st.json(result["details"])


def _render_discovered_wallets(repo, tenant_id: str) -> None:
    st.markdown("**Automatically discovered suspicious wallets**")

    filter_cols = st.columns([2, 1])
    with filter_cols[0]:
        exposure_filter = st.selectbox(
            "Exposure type", ["All", "SANCTION", "MIXER", "SCAM", "RUG_PULL"],
            key="wallet_intel_discovered_filter",
        )
    with filter_cols[1]:
        st.write("")
        refresh = st.button("🔄 Refresh", key="wallet_intel_discovered_refresh")

    exposure_type = None if exposure_filter == "All" else exposure_filter
    flags = repo.list_flags(tenant_id=tenant_id, exposure_type=exposure_type, limit=200)

    if not flags:
        st.info(
            "No wallets discovered yet. Use the Run Discovery tab to scan for "
            "new suspicious wallets, or investigate a specific address above."
        )
        return

    st.caption(f"{len(flags)} flagged wallet(s)")

    display_rows = [
        {
            "Address": f["address"],
            "Chain": f["chain"],
            "Exposure": f["exposure_type"],
            "Severity": f["severity"],
            "Source": f["source"],
            "Discovered Via": f.get("discovered_via_address") or "(direct check)",
            "First Seen": str(f.get("first_seen_at") or "-")[:19],
        }
        for f in flags
    ]
    st.dataframe(display_rows, use_container_width=True, hide_index=True)


def _render_run_discovery(db, tenant_id: str, active_provider: str) -> None:
    st.markdown("**Run an automatic discovery cycle**")
    st.caption(
        "Pulls recent transactions for wallets already flagged, and flags any "
        "new counterparty wallet that has transacted with them -- the "
        "standard 'indirect exposure' technique real sanctions-screening "
        "tools use, rather than scanning the entire chain from scratch."
    )

    from modules.admin.tenant_api_keys import get_provider_key

    etherscan_key = get_provider_key("etherscan", db=db, tenant_id=tenant_id)
    if not etherscan_key:
        st.warning(
            "No Etherscan API key configured for this tenant. Discovery needs "
            "one to pull recent transactions. Add it under Admin Settings below."
        )
        return

    chain = st.selectbox("Chain to scan", CHAIN_OPTIONS, key="wallet_intel_discovery_chain")

    if st.button("▶️ Run Discovery Cycle", key="wallet_intel_run_discovery_btn"):
        from modules.crypto.crypto_wallet_discovery_engine import run_discovery_cycle

        with st.spinner(f"Scanning known-bad {chain} wallets for new counterparties..."):
            result = run_discovery_cycle(
                db=db, tenant_id=tenant_id, chain=chain, api_key=etherscan_key,
            )

        if result["status"] == "ok":
            st.success(
                f"Scanned {result['seeds_scanned']} known-bad wallet(s), "
                f"flagged {result['new_wallets_flagged']} new suspicious wallet(s)."
            )
            if result.get("errors"):
                with st.expander(f"{len(result['errors'])} lookup error(s)"):
                    for err in result["errors"]:
                        st.caption(err)
        else:
            st.error(f"Discovery cycle failed: {result.get('message')}")


def _render_admin_settings(db, repo, tenant_id: str, active_provider: str) -> None:
    st.markdown("**Wallet Intelligence provider**")
    st.caption(
        "Free tier uses OFAC's own sanctions data plus GoPlus Security's free "
        "malicious-address and rug-pull APIs. Configure a premium provider "
        "API key below to route wallet checks through it instead."
    )

    provider_options = ["free", "chainalysis"]
    current_index = provider_options.index(active_provider) if active_provider in provider_options else 0

    selected = st.selectbox(
        "Active provider", provider_options, index=current_index, key="wallet_intel_provider_select",
    )
    if st.button("Save provider", key="wallet_intel_save_provider_btn"):
        repo.set_active_provider(tenant_id, selected)
        st.success(f"Active provider set to: {selected}")

    st.divider()
    st.markdown("**API keys**")
    st.caption(
        "Keys are stored encrypted, scoped to this tenant only, using the "
        "same key management already used elsewhere in this app."
    )

    from modules.admin.tenant_api_keys import set_tenant_key, get_provider_key

    for provider_name, label, help_text in [
        ("etherscan", "Etherscan API key", "Free signup at etherscan.io -- needed for automatic discovery."),
        ("chainalysis", "Chainalysis API key", "Premium provider -- needed only if 'chainalysis' is the active provider above."),
    ]:
        existing = get_provider_key(provider_name, db=db, tenant_id=tenant_id)
        status = "✅ configured" if existing else "not configured"
        new_key = st.text_input(
            f"{label} ({status})", type="password", key=f"wallet_intel_key_{provider_name}", help=help_text,
        )
        if st.button(f"Save {label}", key=f"wallet_intel_save_key_{provider_name}"):
            if new_key.strip():
                set_tenant_key(db, tenant_id, provider_name, new_key.strip(), user_id=None)
                st.success(f"{label} saved.")
            else:
                st.warning("Enter a key before saving.")

    st.divider()
    st.markdown("**Sanctions cache**")
    count = repo.sanctioned_count()
    last_cached = repo.sanctions_last_cached_at()
    st.caption(
        f"{count} sanctioned address(es) cached locally"
        + (f" · last refreshed {last_cached}" if last_cached else " · never refreshed")
    )

    if st.button("🔄 Refresh sanctions list now", key="wallet_intel_refresh_sanctions_btn"):
        from modules.crypto.crypto_sanctions_service import fetch_and_parse_sdn_addresses

        with st.spinner("Fetching the latest OFAC sanctions list..."):
            fetch_result = fetch_and_parse_sdn_addresses()

        if fetch_result["status"] == "ok":
            inserted = repo.replace_sanctioned_addresses(fetch_result["rows"])
            st.success(f"Sanctions cache refreshed: {inserted} address(es) loaded.")
        else:
            st.error(f"Could not refresh sanctions list: {fetch_result.get('message')}")

    st.divider()
    st.markdown("**Scheduled auto-refresh**")
    st.caption(
        "Runs the sanctions cache refresh and discovery cycle automatically "
        "in the background, on top of the manual buttons above -- one "
        "background job for the whole app, not per Streamlit session."
    )

    from modules.db.core import SessionLocal
    from modules.crypto.crypto_wallet_intel_scheduler import get_crypto_wallet_intel_scheduler

    scheduler = get_crypto_wallet_intel_scheduler(db_session_factory=SessionLocal)
    is_running = scheduler.running if scheduler else False

    sched_cols = st.columns(2)
    with sched_cols[0]:
        if not is_running:
            if st.button("▶️ Start auto-refresh", key="wallet_intel_start_scheduler_btn"):
                scheduler.start()
                st.success("Auto-refresh started: sanctions every 6h, discovery every 1h.")
        else:
            st.success("Auto-refresh is running.")
    with sched_cols[1]:
        if is_running:
            if st.button("⏸️ Stop auto-refresh", key="wallet_intel_stop_scheduler_btn"):
                scheduler.stop()
                st.info("Auto-refresh stopped (may take up to 30s to fully halt).")

    for job_name, label in [("sanctions_refresh", "Sanctions refresh"), ("discovery_cycle", "Discovery cycle")]:
        hb = repo.get_job_heartbeat(job_name)
        if hb:
            status_icon = "✅" if hb["status"] == "ok" else "⚠️"
            st.caption(
                f"{status_icon} **{label}**: {hb['status']} -- {hb.get('message') or ''} "
                f"(last run: {hb.get('last_run_at')}, last success: {hb.get('last_success_at') or 'never'})"
            )
        else:
            st.caption(f"⚪ **{label}**: never run yet")