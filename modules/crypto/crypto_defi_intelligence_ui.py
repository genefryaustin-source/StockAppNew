"""
modules/crypto/crypto_defi_intelligence_ui.py

Sprint CR-4: DeFi Intelligence -- UI layer.

TVL Monitoring and Liquidity Pools use endpoints confirmed free from
DefiLlama's own docs. Protocol Risk's TVL-decline signal is always
available (pure local computation); its hack-history signal, and all
of Bridge Monitoring, use endpoints whose free-vs-paid status is
genuinely unconfirmed -- every "unavailable" result is shown as an
honest "this needs a premium DefiLlama plan" message, never silently
hidden or treated as "nothing found".
"""

from __future__ import annotations

import streamlit as st


def render_defi_intelligence(db=None, user=None) -> None:
    st.subheader("🌐 DeFi Intelligence")
    st.caption(
        "TVL monitoring, protocol risk, liquidity pools, and bridge volume "
        "from DefiLlama. Some data (hack history, bridge detail) has a "
        "genuinely unconfirmed free-vs-paid status -- shown honestly as "
        "'unavailable' rather than guessed at."
    )

    if db is None:
        st.info("DeFi Intelligence requires a signed-in session.")
        return

    sub_tabs = st.tabs(["📉 TVL Monitoring", "⚠️ Protocol Risk", "💧 Liquidity Pools", "🌉 Bridge Monitoring"])

    with sub_tabs[0]:
        _render_tvl_monitoring(db)
    with sub_tabs[1]:
        _render_protocol_risk(db)
    with sub_tabs[2]:
        _render_liquidity_pools(db)
    with sub_tabs[3]:
        _render_bridge_monitoring(db)


def _status_message(status: str, message: str) -> None:
    if status == "unavailable":
        st.warning(f"⚠️ Not available: {message}")
    else:
        st.error(f"Error: {message}")


def _render_tvl_monitoring(db) -> None:
    st.markdown("**TVL Monitoring**")
    st.caption("Tracks a protocol's Total Value Locked over time and flags significant declines.")

    protocol_slug = st.text_input(
        "Protocol slug (e.g. aave, curve, uniswap)", key="defi_tvl_protocol_slug",
    )
    threshold = st.slider("Decline alert threshold (%)", min_value=-50, max_value=-5, value=-20, key="defi_tvl_threshold")

    if st.button("🔄 Check TVL", key="defi_tvl_check_btn"):
        if not protocol_slug.strip():
            st.warning("Enter a protocol slug first.")
        else:
            from modules.crypto.crypto_defi_monitoring_engine import check_protocol_tvl

            with st.spinner(f"Fetching TVL for {protocol_slug}..."):
                result = check_protocol_tvl(db=db, protocol_slug=protocol_slug.strip(), decline_alert_threshold_pct=threshold)

            if result["status"] != "ok":
                _status_message(result["status"], result.get("message", ""))
            else:
                st.metric(f"{protocol_slug} TVL", f"${result['tvl_usd']:,.0f}")
                if result["change_pct"] is not None:
                    st.caption(f"Change since last check: {result['change_pct']:+.1f}%")
                if result["flagged"]:
                    st.error(f"🚨 Significant TVL decline flagged for {protocol_slug}.")

    from modules.crypto.crypto_defi_intelligence_repository import get_crypto_defi_intelligence_repository
    repo = get_crypto_defi_intelligence_repository(db=db)

    if protocol_slug.strip():
        history = repo.get_tvl_history(protocol_slug.strip(), limit=20)
        if history:
            st.markdown("**Recent TVL history**")
            st.dataframe(
                [{"Checked At": str(h["checked_at"]), "TVL (USD)": f"{h['tvl_usd']:,.0f}"} for h in history],
                use_container_width=True, hide_index=True,
            )


def _render_protocol_risk(db) -> None:
    st.markdown("**Protocol Risk**")
    st.caption(
        "TVL-decline signal is always available. Hack-history checking "
        "depends on an endpoint whose free-vs-paid status is genuinely "
        "unconfirmed from this environment -- shown honestly either way."
    )

    protocol_slug = st.text_input("Protocol slug", key="defi_risk_protocol_slug")
    protocol_name = st.text_input("Protocol display name (for hack-history matching)", key="defi_risk_protocol_name")

    if st.button("🔍 Check hack history", key="defi_risk_check_hacks_btn"):
        if not protocol_slug.strip():
            st.warning("Enter a protocol slug first.")
        else:
            from modules.crypto.crypto_defi_monitoring_engine import check_protocol_hack_history

            with st.spinner("Checking DefiLlama's hacks dataset..."):
                result = check_protocol_hack_history(
                    db=db, protocol_slug=protocol_slug.strip(),
                    protocol_name=protocol_name.strip() or protocol_slug.strip(),
                )

            if result["status"] != "ok":
                _status_message(result["status"], result.get("message", ""))
            elif result["matches"]:
                st.error(f"🚨 {len(result['matches'])} historical incident(s) found.")
                for m in result["matches"]:
                    st.write(f"- {m.get('name')} ({m.get('date')}) -- {m.get('technique') or 'unspecified technique'}")
            else:
                st.success("No matching incidents found in DefiLlama's hacks dataset.")

    st.divider()
    from modules.crypto.crypto_defi_intelligence_repository import get_crypto_defi_intelligence_repository
    repo = get_crypto_defi_intelligence_repository(db=db)

    flags = repo.list_risk_flags(protocol_slug.strip() or None)
    if not flags:
        st.info("No risk flags recorded yet.")
        return

    st.markdown("**Recorded risk flags**")
    st.dataframe(
        [
            {"Protocol": f["protocol_slug"], "Type": f["risk_type"], "Severity": f["severity"], "Flagged At": str(f["flagged_at"])}
            for f in flags
        ],
        use_container_width=True, hide_index=True,
    )


def _render_liquidity_pools(db) -> None:
    from modules.crypto.crypto_defi_intelligence_repository import get_crypto_defi_intelligence_repository

    repo = get_crypto_defi_intelligence_repository(db=db)

    st.markdown("**Liquidity Pools**")
    st.caption("Pool-level TVL and APY across DeFi protocols.")

    count = len(repo.list_liquidity_pools())
    last_cached = repo.liquidity_pools_last_cached_at()
    st.caption(f"{count} pool(s) cached" + (f" · last refreshed {last_cached}" if last_cached else " · never refreshed"))

    if st.button("🔄 Refresh pools", key="defi_pools_refresh_btn"):
        from modules.crypto.crypto_defi_service import fetch_pools

        with st.spinner("Fetching pool data from DefiLlama..."):
            result = fetch_pools()

        if result["status"] != "ok":
            _status_message(result["status"], result.get("message", ""))
        else:
            inserted = repo.replace_liquidity_pools(result["rows"])
            st.success(f"Refreshed: {inserted} pool(s) loaded.")

    pools = repo.list_liquidity_pools(limit=50)
    if not pools:
        st.info("No pool data yet. Click Refresh above.")
        return

    st.dataframe(
        [
            {
                "Project": p.get("project"), "Chain": p.get("chain"), "Symbol": p.get("symbol"),
                "TVL (USD)": f"{p['tvl_usd']:,.0f}" if p.get("tvl_usd") else "-",
                "APY": f"{p['apy']:.2f}%" if p.get("apy") is not None else "-",
            }
            for p in pools
        ],
        use_container_width=True, hide_index=True,
    )


def _render_bridge_monitoring(db) -> None:
    from modules.crypto.crypto_defi_intelligence_repository import get_crypto_defi_intelligence_repository

    repo = get_crypto_defi_intelligence_repository(db=db)

    st.markdown("**Bridge Monitoring**")
    st.caption(
        "Cross-chain bridge volume -- genuinely unconfirmed free-vs-paid "
        "status for this specific data. Shown honestly if it turns out to "
        "require a paid plan."
    )

    chain = st.selectbox("Chain", ["ethereum", "arbitrum", "polygon", "optimism", "base"], key="defi_bridge_chain")

    if st.button("🔄 Refresh bridge volume", key="defi_bridge_refresh_btn"):
        from modules.crypto.crypto_defi_service import fetch_bridge_volumes

        with st.spinner(f"Fetching bridge volume for {chain}..."):
            result = fetch_bridge_volumes(chain)

        if result["status"] != "ok":
            _status_message(result["status"], result.get("message", ""))
        else:
            inserted = repo.replace_bridge_volumes(result["rows"])
            st.success(f"Refreshed: {inserted} bridge(s) loaded.")

    last_cached = repo.bridge_volumes_last_cached_at()
    if last_cached:
        st.caption(f"Last refreshed: {last_cached}")

    bridges = repo.list_bridge_volumes()
    if not bridges:
        st.info("No bridge volume data cached yet.")
        return

    st.dataframe(
        [
            {"Bridge": b.get("bridge_name"), "Chain": b.get("chain"),
             "24h Volume (USD)": f"{b['volume_24h_usd']:,.0f}" if b.get("volume_24h_usd") else "-"}
            for b in bridges
        ],
        use_container_width=True, hide_index=True,
    )