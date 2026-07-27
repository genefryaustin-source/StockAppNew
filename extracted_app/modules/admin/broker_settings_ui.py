"""
modules/admin/broker_settings_ui.py

"Brokers" admin tab -- lets a tenant admin (or super admin managing a
selected tenant) turn on the broker/execution providers their traders
should be able to pick from in Trading & Execution. Most tenants only
use one real broker, so everything except "Paper" is off by default;
turning one on here is what makes it show up in that dropdown at all.

Wire into admin_ui.py's tab structure the same way api_keys_tab is:

    from modules.admin.broker_settings_ui import render_broker_settings_tab

    (
        tab_users, tab_plan, tab_tenants, api_keys_tab,
        broker_settings_tab,                              # <-- add this
        tab_cleanup, ...
    ) = st.tabs([
        "👤 Users", "💳 Plan Management", "🏢 Tenants", "🔑 API Keys",
        "🏦 Brokers",                                      # <-- add this
        "🧹 Universe Cleanup", ...
    ])

    with broker_settings_tab:
        render_broker_settings_tab(db, user)
"""

from __future__ import annotations

import streamlit as st

from modules.portfolio.brokers.factory import available_brokers
from modules.portfolio.brokers.broker_settings import (
    list_broker_settings,
    set_broker_enabled,
)

# code -> (display label, one-line description)
_BROKER_INFO = {
    "alpaca": ("Alpaca", "Commission-free equities/crypto brokerage. Key + secret, paper or live."),
    "tradier": ("Tradier", "Equities/options brokerage. Access token + account ID, sandbox or production."),
    "ibkr": ("Interactive Brokers", "Requires a self-hosted, browser-authenticated Client Portal Gateway."),
    "ondo": ("Ondo Finance", "Tokenized US stocks, ETFs, commodities, and Treasuries (OUSG/USDY)."),
    "securitize": ("Securitize", "Institutional tokenized funds (e.g. BlackRock's BUIDL) and private credit."),
    "tokenized_custom": ("Custom Tokenized Asset Provider", "Any other RWA venue via a configurable REST endpoint."),
    "ccxt": ("Crypto Exchange (ccxt)", "Real spot trading on Binance/Coinbase/Kraken/100+ exchanges via one unified API."),
}


def _active_tenant_id(user) -> str | None:
    if user.get("role") == "super_admin":
        return st.session_state.get("admin_selected_tenant")
    return user.get("tenant_id")


def render_broker_settings_tab(db, user):
    st.subheader("🏦 Brokers")
    st.caption(
        "Choose which broker(s) traders on this tenant can select in Trading & Execution. "
        "\"Paper\" is always available. Enabling a broker here doesn't connect it by itself -- "
        "credentials still need to be added under **Admin > API Keys**."
    )

    tenant_id = _active_tenant_id(user)
    if not tenant_id:
        st.warning("No active tenant context.")
        return

    role = user.get("role")
    if role not in ("tenant_admin", "super_admin"):
        st.info("Only tenant admins and super admins can manage broker access.")
        return

    real_brokers = [b for b in available_brokers() if b != "paper"]
    settings = list_broker_settings(db, tenant_id)

    st.markdown("#### Paper")
    st.caption("Simulated trading against real market data — always on, no credentials needed.")
    st.divider()

    for broker_name in real_brokers:
        label, description = _BROKER_INFO.get(broker_name, (broker_name.title(), ""))
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(f"**{label}**")
            st.caption(description)
        with c2:
            new_value = st.toggle(
                "Enabled",
                value=settings.get(broker_name, False),
                key=f"broker_toggle_{tenant_id}_{broker_name}",
            )
        if new_value != settings.get(broker_name, False):
            set_broker_enabled(db, tenant_id, broker_name, new_value, user_id=user.get("user_id"))
            st.success(f"{label} is now {'enabled' if new_value else 'disabled'} for this tenant.")
            st.rerun()
        st.divider()

    enabled_now = ["Paper"] + [
        _BROKER_INFO.get(b, (b.title(),))[0] for b in real_brokers if settings.get(b, False)
    ]
    st.caption(f"Currently selectable in Trading & Execution: {', '.join(enabled_now)}")
