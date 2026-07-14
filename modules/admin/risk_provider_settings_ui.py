"""
modules/admin/risk_provider_settings_ui.py

"Risk Providers" admin tab -- lets a tenant admin (or super admin managing
a selected tenant) turn on external risk-analytics vendors (PortfolioScience
RiskAPI, FactSet Open:Risk, or a Custom REST provider) for the Internal
Risk Layer. Mirrors modules.admin.broker_settings_ui exactly in structure.

Wire into admin_ui.py the same way broker_settings_tab is:

    from modules.admin.risk_provider_settings_ui import render_risk_provider_settings_tab

    (
        tab_users, tab_plan, tab_tenants, api_keys_tab, broker_settings_tab,
        risk_provider_settings_tab,                        # <-- add this
        tab_cleanup, ...
    ) = st.tabs([
        "👤 Users", "💳 Plan Management", "🏢 Tenants", "🔑 API Keys",
        "🏦 Brokers", "🧮 Risk Providers",                  # <-- add this
        "🧹 Universe Cleanup", ...
    ])

    with risk_provider_settings_tab:
        render_risk_provider_settings_tab(db, user)
"""

from __future__ import annotations

import streamlit as st

from modules.risk_providers.registry import available_risk_providers, RISK_PROVIDER_INFO
from modules.risk_providers.provider_settings import (
    list_provider_settings,
    set_provider_enabled,
    set_provider_config,
)


def _active_tenant_id(user) -> str | None:
    if user.get("role") == "super_admin":
        return st.session_state.get("admin_selected_tenant")
    return user.get("tenant_id")


def render_risk_provider_settings_tab(db, user):
    st.subheader("🧮 Risk Providers")
    st.caption(
        "Turn on external risk-analytics vendors as a cross-check alongside the Internal Risk "
        "Layer's own VaR/concentration math. Enabling a vendor here doesn't connect it by "
        "itself -- credentials still need to be added under **Admin > API Keys**."
    )

    tenant_id = _active_tenant_id(user)
    if not tenant_id:
        st.warning("No active tenant context.")
        return

    role = user.get("role")
    if role not in ("tenant_admin", "super_admin"):
        st.info("Only tenant admins and super admins can manage risk provider access.")
        settings = list_provider_settings(db, tenant_id)
        st.json({k: v["enabled"] for k, v in settings.items()})
        return

    settings = list_provider_settings(db, tenant_id)

    for provider_name in available_risk_providers():
        label, description = RISK_PROVIDER_INFO.get(provider_name, (provider_name.title(), ""))
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(f"**{label}**")
            st.caption(description)
        with c2:
            new_value = st.toggle(
                "Enabled",
                value=settings[provider_name]["enabled"],
                key=f"riskprovider_toggle_{tenant_id}_{provider_name}",
            )
        if new_value != settings[provider_name]["enabled"]:
            set_provider_enabled(db, tenant_id, provider_name, new_value, user_id=user.get("user_id"))
            st.success(f"{label} is now {'enabled' if new_value else 'disabled'} for this tenant.")
            st.rerun()

        if provider_name == "custom":
            with st.expander("Custom Risk Provider field mapping"):
                cfg = settings[provider_name]["config"]
                request_path = st.text_input("Request path (appended to base URL)",
                                              value=cfg.get("request_path", "/risk"),
                                              key=f"riskprovider_reqpath_{tenant_id}")
                var_path = st.text_input("Response field for VaR (dotted path)",
                                          value=cfg.get("response_var_path", "var"),
                                          key=f"riskprovider_varpath_{tenant_id}")
                es_path = st.text_input("Response field for Expected Shortfall (dotted path)",
                                         value=cfg.get("response_es_path", "expected_shortfall"),
                                         key=f"riskprovider_espath_{tenant_id}")
                if st.button("Save mapping", key=f"riskprovider_savecfg_{tenant_id}"):
                    set_provider_config(db, tenant_id, "custom", {
                        **cfg,
                        "request_path": request_path,
                        "response_var_path": var_path,
                        "response_es_path": es_path,
                    }, user_id=user.get("user_id"))
                    st.success("Saved custom risk provider mapping.")
                    st.rerun()

        st.divider()

    enabled_now = [
        RISK_PROVIDER_INFO.get(n, (n.title(),))[0]
        for n, s in settings.items() if s["enabled"]
    ]
    st.caption(f"Currently active in the Risk Layer: {', '.join(enabled_now) if enabled_now else 'None'}")
