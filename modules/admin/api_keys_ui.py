"""
modules/admin/api_keys_ui.py

"API Keys" admin tab -- lets a tenant bring their own provider API keys
(market data, AI, etc.) instead of relying on the platform's single
shared Streamlit Cloud secret.

Wire into admin_ui.py's existing tab structure, e.g.:

    from modules.admin.api_keys_ui import render_api_keys_tab

    (
        tab_users, tab_plan, tab_tenants, tab_cleanup,
        provider_health_tab, provider_operations_tab,
        analytics_freshness_tab, api_keys_tab,   # <-- add this
    ) = st.tabs([
        "👤 Users", "💳 Plan Management", "🏢 Tenants", "🧹 Universe Cleanup",
        "🔌 Provider Health", "🚀 Provider Operations", "📊 Universe Analytics",
        "🔑 API Keys",   # <-- add this
    ])

    with api_keys_tab:
        render_api_keys_tab(db, user)

Visible to both tenant_admin (manages their own tenant) and super_admin
(manages whichever tenant is selected via the existing tenant selector
at the top of the Admin Console).
"""

from __future__ import annotations

import streamlit as st

from modules.admin.tenant_api_keys import (
    KNOWN_PROVIDERS,
    PLATFORM_KEY_GRACE_PERIOD_DAYS,
    set_tenant_key,
    delete_tenant_key,
    list_tenant_keys,
    grace_period_status,
    set_tenant_grace_override,
)

# code -> (label, signup_url)
_PROVIDER_INFO = {code: (label, url) for code, label, url in KNOWN_PROVIDERS}


def _active_tenant_id(user) -> str | None:
    if user.get("role") == "super_admin":
        return st.session_state.get("admin_selected_tenant")
    return user.get("tenant_id")


def render_api_keys_tab(db, user):
    st.subheader("🔑 API Keys")
    st.caption(
        "Bring your own provider keys instead of using the platform's shared "
        "key. Once you set your own key below, it's used instead of the "
        "platform's for every feature that needs it."
    )

    tenant_id = _active_tenant_id(user)
    if not tenant_id:
        st.warning("No active tenant context.")
        return

    role = user.get("role")
    if role not in ("tenant_admin", "super_admin"):
        st.info("Only tenant admins and super admins can manage API keys.")
        return

    # --- Grace period banner -----------------------------------------
    status = grace_period_status(db, tenant_id)
    if status["unlimited"]:
        st.info(
            "✅ A super admin has exempted this tenant from the platform "
            "API key grace period -- the shared key works indefinitely "
            "here, with no expiry."
        )
    elif status["created_at"] is not None:
        effective_days = status["days_override"] or PLATFORM_KEY_GRACE_PERIOD_DAYS
        if status["expired"]:
            st.error(
                f"⏰ **The platform's shared API key is no longer available to this "
                f"account.** It's only provided for the first {effective_days} "
                "days after signup. Any feature below that doesn't have your own key set "
                "will stop working until you add one -- it only takes a minute, see the "
                "links next to each provider below."
            )
        elif status["days_left"] is not None and status["days_left"] <= 3:
            st.warning(
                f"⏳ **{status['days_left']} day(s) left** on the platform's shared API key "
                f"for this account. After {effective_days} days from signup, "
                "any feature without your own key set will stop working. Add your keys below "
                "now to avoid any interruption."
            )
        else:
            st.info(
                f"ℹ️ The platform's shared API key is available for the first "
                f"{effective_days} days after signup "
                f"({status['days_left']} day(s) remaining). After that, features will "
                "need your own key configured below to keep working."
            )

    # --- Super-admin-only grace period override ------------------------
    if role == "super_admin":
        with st.expander("🛠️ Super admin: override this tenant's grace period"):
            st.caption(
                "Applies to whichever tenant is currently selected above. Use this to "
                "give a specific tenant more time, exempt them entirely, or revert "
                f"them back to the platform default ({PLATFORM_KEY_GRACE_PERIOD_DAYS} days)."
            )

            current = "Unlimited" if status["unlimited"] else (
                f"{status['days_override']} days (custom)" if status["days_override"]
                else f"{PLATFORM_KEY_GRACE_PERIOD_DAYS} days (default)"
            )
            st.write(f"**Current setting:** {current}")

            ov1, ov2, ov3 = st.columns(3)

            with ov1:
                if st.button("♾️ Make unlimited", key="grace_override_unlimited", use_container_width=True):
                    set_tenant_grace_override(db, tenant_id, unlimited=True)
                    st.success("This tenant's platform key will no longer expire.")
                    st.rerun()

            with ov2:
                custom_days = st.number_input(
                    "Custom days", min_value=1, max_value=3650,
                    value=status["days_override"] or PLATFORM_KEY_GRACE_PERIOD_DAYS,
                    key="grace_override_days_input", label_visibility="collapsed",
                )
                if st.button("Set custom days", key="grace_override_set_days", use_container_width=True):
                    set_tenant_grace_override(db, tenant_id, days_override=int(custom_days))
                    st.success(f"This tenant's grace period is now {int(custom_days)} days.")
                    st.rerun()

            with ov3:
                if st.button("↩️ Revert to default", key="grace_override_clear", use_container_width=True):
                    set_tenant_grace_override(db, tenant_id, clear_override=True)
                    st.success(f"Reverted to the platform default ({PLATFORM_KEY_GRACE_PERIOD_DAYS} days).")
                    st.rerun()

    existing = {row.provider: row for row in list_tenant_keys(db, tenant_id)}

    if existing:
        st.markdown("#### Currently configured")
        for provider, row in existing.items():
            label, _url = _PROVIDER_INFO.get(provider, (provider, None))
            c1, c2, c3 = st.columns([3, 2, 1])
            c1.write(f"**{label}**")
            c2.caption(
                f"...{row.key_suffix}  •  updated "
                f"{row.updated_at.strftime('%Y-%m-%d %H:%M') if row.updated_at else '—'}"
            )
            if c3.button("Remove", key=f"apikey_remove_{provider}"):
                delete_tenant_key(db, tenant_id, provider)
                st.success(f"Removed your {label} key. Falling back to the platform key.")
                st.rerun()
        st.divider()
    else:
        st.info("No tenant-specific keys configured yet -- using the platform's shared keys.")

    st.markdown("#### Add / update a key")
    st.caption("Don't have a key for a provider yet? Click its link below to get one.")

    # Quick-reference links to every provider's key page, so there's
    # nowhere to hunt around -- click, sign up, paste, save.
    link_cols = st.columns(len(KNOWN_PROVIDERS))
    for col, (code, label, url) in zip(link_cols, KNOWN_PROVIDERS):
        col.link_button(label, url, use_container_width=True)

    provider_labels = {code: label for code, label, _url in KNOWN_PROVIDERS}
    selected_provider = st.selectbox(
        "Provider",
        list(provider_labels.keys()),
        format_func=lambda code: provider_labels[code],
        key="apikey_provider_select",
    )

    new_key_value = st.text_input(
        "API key",
        type="password",
        key="apikey_new_value",
        placeholder="Paste the key here -- it's encrypted before it's stored.",
    )

    if st.button("💾 Save key", key="apikey_save_btn"):
        if not new_key_value.strip():
            st.warning("Enter a key value first.")
        else:
            try:
                set_tenant_key(
                    db, tenant_id, selected_provider, new_key_value,
                    user_id=user.get("user_id"),
                )
                st.success(
                    f"Saved your {provider_labels[selected_provider]} key. "
                    "It will be used instead of the platform's shared key "
                    "from now on."
                )
                st.rerun()
            except Exception as e:
                st.error(f"Could not save key: {e}")