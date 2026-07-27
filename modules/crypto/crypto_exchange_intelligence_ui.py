"""
modules/crypto/crypto_exchange_intelligence_ui.py

Sprint CR-3: Exchange Intelligence -- UI layer.

Exchange Risk Scoring and Liquidity Monitoring are fully automated
(CoinGecko's free, no-key /exchanges endpoints). Reserve Monitoring
requires analyst-entered addresses with a required source citation --
confirmed no free API (CoinGecko or DefiLlama) exposes this data
directly, so it has to be human-sourced, the same principle already
applied to CR-2's Threat Actors/Campaigns.
"""

from __future__ import annotations

import streamlit as st

CHAIN_OPTIONS = ["ethereum", "bsc", "polygon", "arbitrum", "optimism", "base", "avalanche"]


def render_exchange_intelligence(db=None, user=None) -> None:
    st.subheader("🏦 Exchange Intelligence")
    st.caption(
        "Exchange risk scoring and liquidity from CoinGecko's free exchange "
        "data, plus reserve monitoring for analyst-verified exchange wallets."
    )

    if db is None or user is None:
        st.info("Exchange Intelligence requires a signed-in session.")
        return

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        st.warning("No tenant context available -- Exchange Intelligence is disabled.")
        return

    sub_tabs = st.tabs(["📊 Risk Scoring", "💧 Liquidity Monitoring", "🏛️ Reserve Monitoring"])

    with sub_tabs[0]:
        _render_risk_scoring(db)
    with sub_tabs[1]:
        _render_liquidity_monitoring(db)
    with sub_tabs[2]:
        _render_reserve_monitoring(db, tenant_id)


def _render_risk_scoring(db) -> None:
    from modules.crypto.crypto_exchange_intelligence_repository import get_crypto_exchange_intelligence_repository

    repo = get_crypto_exchange_intelligence_repository(db=db)

    st.markdown("**Exchange Risk Scoring**")
    st.caption("CoinGecko's Trust Score (0-10): traffic, liquidity, API coverage, cybersecurity, and proof-of-reserves disclosure.")

    count = len(repo.list_exchange_risk_scores())
    last_cached = repo.risk_scores_last_cached_at()
    st.caption(
        f"{count} exchange(s) cached"
        + (f" · last refreshed {last_cached}" if last_cached else " · never refreshed")
    )

    if st.button("🔄 Refresh exchange list", key="exch_intel_refresh_risk_btn"):
        from modules.crypto.crypto_exchange_risk_service import fetch_exchange_risk_scores

        with st.spinner("Fetching exchange data from CoinGecko..."):
            result = fetch_exchange_risk_scores()

        if result["status"] == "ok":
            inserted = repo.replace_exchange_risk_scores(result["rows"])
            st.success(f"Refreshed: {inserted} exchange(s) loaded.")
        else:
            st.error(f"Could not refresh: {result.get('message')}")

    scores = repo.list_exchange_risk_scores()
    if not scores:
        st.info("No exchange data yet. Click Refresh above.")
        return

    st.dataframe(
        [
            {
                "Exchange": s["name"],
                "Trust Score": s.get("trust_score"),
                "Rank": s.get("trust_score_rank"),
                "24h Volume (BTC)": f"{s['trade_volume_24h_btc']:,.1f}" if s.get("trade_volume_24h_btc") else "-",
                "Country": s.get("country") or "-",
                "Established": s.get("year_established") or "-",
            }
            for s in scores
        ],
        use_container_width=True, hide_index=True,
    )


def _render_liquidity_monitoring(db) -> None:
    from modules.crypto.crypto_exchange_intelligence_repository import get_crypto_exchange_intelligence_repository

    repo = get_crypto_exchange_intelligence_repository(db=db)

    st.markdown("**Liquidity Monitoring**")
    st.caption(
        "Bid/ask spread and cost to move the price by a fixed amount -- a "
        "genuine liquidity signal, not just raw trading volume. Tighter "
        "spread and higher cost-to-move both indicate deeper, healthier "
        "liquidity."
    )

    scores = repo.list_exchange_risk_scores()
    if not scores:
        st.info("Refresh the exchange list under Risk Scoring first.")
        return

    exchange_options = {s["name"]: s["exchange_id"] for s in scores}
    exchange_name = st.selectbox("Exchange", list(exchange_options.keys()), key="exch_intel_liquidity_select")
    exchange_id = exchange_options[exchange_name]

    if st.button("🔄 Check liquidity", key="exch_intel_check_liquidity_btn"):
        from modules.crypto.crypto_exchange_risk_service import fetch_exchange_liquidity

        with st.spinner(f"Fetching ticker data for {exchange_name}..."):
            result = fetch_exchange_liquidity(exchange_id)

        if result["status"] == "ok":
            for row in result["rows"]:
                repo.add_liquidity_snapshot(
                    exchange_id=exchange_id, base=row["base"], target=row["target"],
                    bid_ask_spread_percentage=row["bid_ask_spread_percentage"],
                    cost_to_move_up_usd=row["cost_to_move_up_usd"],
                    cost_to_move_down_usd=row["cost_to_move_down_usd"], volume=row["volume"],
                )
            st.success(f"Checked {len(result['rows'])} pair(s).")
        else:
            st.error(f"Could not fetch liquidity: {result.get('message')}")

    snapshots = repo.list_latest_liquidity_snapshots(exchange_id)
    if not snapshots:
        st.info("No liquidity data yet for this exchange. Click Check liquidity above.")
        return

    st.dataframe(
        [
            {
                "Pair": f"{s['base']}/{s['target']}",
                "Spread %": f"{s['bid_ask_spread_percentage']:.4f}" if s.get("bid_ask_spread_percentage") is not None else "-",
                "Cost to Move Up ($)": f"{s['cost_to_move_up_usd']:,.0f}" if s.get("cost_to_move_up_usd") else "-",
                "Cost to Move Down ($)": f"{s['cost_to_move_down_usd']:,.0f}" if s.get("cost_to_move_down_usd") else "-",
                "24h Volume": f"{s['volume']:,.1f}" if s.get("volume") else "-",
            }
            for s in snapshots
        ],
        use_container_width=True, hide_index=True,
    )


def _render_reserve_monitoring(db, tenant_id: str) -> None:
    from modules.crypto.crypto_exchange_intelligence_repository import get_crypto_exchange_intelligence_repository

    repo = get_crypto_exchange_intelligence_repository(db=db)

    st.markdown("**Reserve Monitoring**")
    st.caption(
        "No free API exposes exchange proof-of-reserves data directly -- "
        "register a wallet address you've confirmed belongs to an "
        "exchange's reserves, with a link to where you confirmed it. "
        "Balance is tracked over time to flag significant outflows."
    )

    with st.expander("➕ Register a reserve address"):
        exchange_name = st.text_input("Exchange name", key="exch_intel_reserve_name")
        address = st.text_input("Wallet address", key="exch_intel_reserve_address")
        chain = st.selectbox("Chain", CHAIN_OPTIONS, key="exch_intel_reserve_chain")
        source_url = st.text_input(
            "Source URL (required)", placeholder="https://...",
            help="Where you confirmed this address belongs to the exchange -- e.g. their own proof-of-reserves page.",
            key="exch_intel_reserve_source",
        )
        source_note = st.text_area("Notes (optional)", key="exch_intel_reserve_note")

        if st.button("Register", key="exch_intel_register_reserve_btn"):
            if not exchange_name.strip() or not address.strip():
                st.warning("Enter both an exchange name and an address.")
            elif not source_url.strip():
                st.warning("A source URL is required -- reserve addresses must be traceable.")
            else:
                try:
                    repo.add_reserve_address(
                        tenant_id=tenant_id, exchange_name=exchange_name.strip(), address=address.strip(),
                        chain=chain, source_url=source_url.strip(), source_note=source_note.strip() or None,
                    )
                    st.success(f"Registered {address} for {exchange_name}.")
                except ValueError as exc:
                    st.error(str(exc))

    st.divider()

    from modules.admin.tenant_api_keys import get_provider_key
    etherscan_key = get_provider_key("etherscan", db=db, tenant_id=tenant_id)

    reserves = repo.list_reserve_addresses(tenant_id=tenant_id)
    if not reserves:
        st.info("No reserve addresses registered yet.")
        return

    if not etherscan_key:
        st.warning("No Etherscan API key configured (needed to check balances). Add one in Wallet Intelligence > Admin Settings.")
    else:
        threshold = st.slider(
            "Outflow alert threshold (%)", min_value=-50, max_value=-1, value=-10,
            key="exch_intel_outflow_threshold",
        )
        if st.button("🔄 Check all reserve balances", key="exch_intel_check_reserves_btn"):
            from modules.crypto.crypto_reserve_monitoring_service import check_all_reserve_addresses

            with st.spinner(f"Checking {len(reserves)} reserve address(es)..."):
                result = check_all_reserve_addresses(
                    db=db, tenant_id=tenant_id, api_key=etherscan_key, outflow_alert_threshold_pct=threshold,
                )

            st.success(f"Checked {result['checked']} address(es).")
            for alert in result["alerts"]:
                st.error(
                    f"🚨 {alert['exchange_name']}: balance dropped {alert['change_pct']:.1f}% "
                    f"({alert['previous_balance_native']:,.2f} \u2192 {alert['balance_native']:,.2f})"
                )
            for err in result.get("errors", []):
                st.caption(f"⚠️ {err}")

    for reserve in reserves:
        latest = repo.get_latest_reserve_balance(reserve["id"])
        with st.expander(f"🏛️ {reserve['exchange_name']} -- {reserve['address']} ({reserve['chain']})"):
            st.caption(f"Source: {reserve['source_url']}")
            if reserve.get("source_note"):
                st.write(reserve["source_note"])
            if latest:
                st.metric("Latest balance", f"{latest['balance_native']:,.4f}")
                st.caption(f"Last checked: {latest['checked_at']}")
            else:
                st.caption("No balance checks yet.")