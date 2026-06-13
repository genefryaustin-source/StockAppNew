"""
modules/auth/custom_plan_ui.py

Super Admin — Custom Plan Manager UI.

Allows super_admin to:
  1. View all tenants and their current plans
  2. Change a tenant's base plan
  3. Toggle individual modules on/off per tenant
  4. Apply preset bundles (e.g. "Enterprise Bundle")
  5. View module access audit trail

Embed in Admin page:
    from modules.auth.custom_plan_ui import render_custom_plan_manager
    render_custom_plan_manager(db, user)
"""
from __future__ import annotations
import streamlit as st
import pandas as pd
from modules.auth.custom_plan_service import (
    ALL_MODULES, MODULE_CATEGORIES,
    get_all_tenants, get_tenant_plan, set_tenant_plan,
    get_module_overrides, set_module_override,
    set_bulk_module_overrides, clear_all_overrides,
    check_module_access, ensure_tables,
)
from modules.auth.entitlements import PLAN_RANK, PLAN_META, FEATURE_PLANS

GREEN = "#1D9E75"
RED   = "#E24B4A"
BLUE  = "#2E75B6"


def render_custom_plan_manager(db, user: dict):
    """Full custom plan manager — only visible to super_admin."""
    if (user or {}).get("role") != "super_admin":
        st.warning("🔒 Super Admin access required.")
        return

    ensure_tables(db)

    st.header("🎛️ Custom Plan Manager")
    st.caption(
        "Control exactly which modules each tenant can access. "
        "Override the default plan-based entitlements at the tenant level."
    )

    tabs = st.tabs([
        "🏢 Tenant Overview",
        "⚙️ Module Configuration",
        "📦 Plan Presets",
        "📋 Access Audit",
    ])

    with tabs[0]: _render_tenant_overview(db, user)
    with tabs[1]: _render_module_config(db, user)
    with tabs[2]: _render_presets(db, user)
    with tabs[3]: _render_audit(db)


# ══════════════════════════════════════════════════════════════
# TAB 1 — TENANT OVERVIEW
# ══════════════════════════════════════════════════════════════

def _render_tenant_overview(db, user: dict):
    st.subheader("🏢 Tenant Overview")
    st.caption("All tenants, their current plan, and user count.")

    tenants = get_all_tenants(db)
    if not tenants:
        st.info("No tenants found.")
        return

    # Summary metrics
    plans = [t["base_plan"] for t in tenants]
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Total Tenants", len(tenants))
    c2.metric("🎓 Student",    plans.count("student"))
    c3.metric("🥉 Starter",    plans.count("starter"))
    c4.metric("🥈 Pro",        plans.count("pro"))
    c5.metric("🥇 Team",       plans.count("team"))

    st.markdown("---")

    for t in tenants:
        tid      = t["tenant_id"]
        plan     = t["base_plan"]
        custom   = t["custom_name"]
        n_users  = t["user_count"]
        meta     = PLAN_META.get(plan, PLAN_META["starter"])
        overrides = get_module_overrides(db, tid)
        n_overrides = len(overrides)

        with st.container():
            col_info, col_plan, col_actions = st.columns([3, 2, 2])

            with col_info:
                display_name = custom or tid
                st.markdown(
                    f"**{display_name}**"
                    + (f" `{tid}`" if custom else "")
                )
                st.caption(f"👥 {n_users} users"
                           + (f" · ⚙️ {n_overrides} module overrides" if n_overrides else ""))

            with col_plan:
                st.markdown(
                    f"<span style='color:{meta['color']}'>"
                    f"{meta['emoji']} **{meta['name']}**</span> "
                    f"<span style='color:#8B949E;font-size:12px'>{meta['price']}</span>",
                    unsafe_allow_html=True,
                )

            with col_actions:
                new_plan = st.selectbox(
                    "Change plan",
                    ["student","starter","pro","team"],
                    index=["student","starter","pro","team"].index(plan),
                    key=f"plan_sel_{tid}",
                    label_visibility="collapsed",
                )
                if st.button("Save", key=f"plan_save_{tid}",
                              use_container_width=True):
                    set_tenant_plan(db, tid, new_plan,
                                    updated_by=user.get("email"))
                    st.success(f"✅ {tid} → {new_plan}")
                    st.rerun()

        st.markdown("---")


# ══════════════════════════════════════════════════════════════
# TAB 2 — MODULE CONFIGURATION
# ══════════════════════════════════════════════════════════════

def _render_module_config(db, user: dict):
    st.subheader("⚙️ Module Configuration")
    st.caption(
        "Toggle individual modules on/off per tenant. "
        "Overrides take precedence over the tenant's base plan — "
        "you can grant Pro features to a Starter tenant, or restrict Pro features."
    )

    tenants = get_all_tenants(db)
    if not tenants:
        st.info("No tenants found.")
        return

    # Tenant selector
    tenant_opts = {t["tenant_id"]: f"{t['tenant_id']} ({t['base_plan']})"
                   for t in tenants}
    sel_tid = st.selectbox(
        "Select Tenant",
        list(tenant_opts.keys()),
        format_func=lambda x: tenant_opts[x],
        key="mod_cfg_tenant",
    )

    if not sel_tid:
        return

    tenant_plan_info = get_tenant_plan(db, sel_tid)
    base_plan        = tenant_plan_info["base_plan"]
    overrides        = get_module_overrides(db, sel_tid)
    plan_meta        = PLAN_META.get(base_plan, PLAN_META["starter"])

    st.markdown(
        f"**{sel_tid}** — Base plan: "
        f"<span style='color:{plan_meta['color']}'>"
        f"{plan_meta['emoji']} {plan_meta['name']}</span>",
        unsafe_allow_html=True,
    )

    # Custom plan name
    col_name, col_save_name = st.columns([3,1])
    with col_name:
        custom_name = st.text_input(
            "Custom plan label (optional)",
            value=tenant_plan_info.get("custom_name") or "",
            placeholder="e.g. 'Enterprise Bundle', 'Hedge Fund Pro'",
            key=f"custom_name_{sel_tid}",
        )
    with col_save_name:
        st.write("")
        if st.button("Save Label", key=f"save_label_{sel_tid}",
                      use_container_width=True):
            set_tenant_plan(db, sel_tid, base_plan, custom_name=custom_name,
                            updated_by=user.get("email"))
            st.success("✅ Label saved")

    st.markdown("---")
    st.markdown("#### Module Access Toggles")
    st.caption(
        "🟢 **Enabled** (plan default) · "
        "🔵 **Override ON** (granted above plan) · "
        "🔴 **Override OFF** (revoked below plan) · "
        "⚫ **Plan default OFF**"
    )

    # Show by category with toggles
    pending_changes = {}

    for category, modules in MODULE_CATEGORIES.items():
        st.markdown(f"**{category}**")
        cols = st.columns(3)
        for i, module in enumerate(modules):
            with cols[i % 3]:
                # Determine default from plan
                required_plan = FEATURE_PLANS.get(module, "pro")
                plan_allows   = (PLAN_RANK.get(base_plan, 1) >=
                                  PLAN_RANK.get(required_plan, 1))

                # Current state
                if module in overrides:
                    current = overrides[module]
                    is_override = True
                else:
                    current = plan_allows
                    is_override = False

                # Status label
                if is_override and current and not plan_allows:
                    label = f"🔵 {module}"     # override grant
                elif is_override and not current and plan_allows:
                    label = f"🔴 {module}"     # override revoke
                elif current:
                    label = f"🟢 {module}"     # plan default on
                else:
                    label = f"⚫ {module}"     # plan default off

                new_val = st.toggle(
                    label,
                    value=current,
                    key=f"mod_{sel_tid}_{module}",
                )

                # Track changes
                if new_val != current:
                    pending_changes[module] = new_val

        st.write("")

    # Save changes
    if pending_changes:
        st.info(
            f"**{len(pending_changes)} unsaved change(s):** "
            + ", ".join(
                f"{'✅' if v else '❌'} {m}"
                for m, v in pending_changes.items()
            )
        )
        col_save, col_cancel = st.columns([1, 1])
        with col_save:
            if st.button("💾 Save All Changes", type="primary",
                          key=f"save_overrides_{sel_tid}",
                          use_container_width=True):
                set_bulk_module_overrides(db, sel_tid, pending_changes,
                                           set_by=user.get("email"))
                st.success(f"✅ {len(pending_changes)} module(s) updated")
                st.rerun()
        with col_cancel:
            if st.button("↩ Reset to Plan Defaults",
                          key=f"reset_{sel_tid}",
                          use_container_width=True):
                clear_all_overrides(db, sel_tid)
                st.success("✅ All overrides cleared")
                st.rerun()

    # Current overrides summary
    if overrides:
        st.markdown("#### Active Overrides")
        rows = []
        for mod, enabled in overrides.items():
            req_plan = FEATURE_PLANS.get(mod, "pro")
            plan_default = (PLAN_RANK.get(base_plan,1) >= PLAN_RANK.get(req_plan,1))
            rows.append({
                "Module":        mod,
                "Override":      "✅ Enabled" if enabled else "❌ Disabled",
                "Plan Default":  "✅" if plan_default else "❌",
                "Effect":        ("Granted above plan" if enabled and not plan_default
                                  else "Revoked below plan" if not enabled and plan_default
                                  else "Same as plan"),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        if st.button("🗑 Clear All Overrides", key=f"clear_all_{sel_tid}"):
            clear_all_overrides(db, sel_tid)
            st.success("Cleared")
            st.rerun()


# ══════════════════════════════════════════════════════════════
# TAB 3 — PLAN PRESETS
# ══════════════════════════════════════════════════════════════

PRESETS = {
    "🏦 RIA / Wealth Manager": {
        "description": "Full research suite for registered investment advisors",
        "base_plan":   "pro",
        "enable":      ["Team Collaboration", "Analyst Consensus",
                        "Research Reports", "Export / Sheets",
                        "Social Sentiment"],
        "disable":     ["Crypto", "Options Trading"],
    },
    "📈 Active Trader": {
        "description": "Trading-focused with real-time data and options",
        "base_plan":   "pro",
        "enable":      ["Options Trading", "Options Flow", "Intraday Charts",
                        "Smart Money", "Alerts"],
        "disable":     ["Team Collaboration"],
    },
    "🎓 University / Education": {
        "description": "Educational access with core research tools",
        "base_plan":   "starter",
        "enable":      ["Screener", "Analytics", "Stock Dashboard",
                        "Formula Builder", "AI Rankings"],
        "disable":     ["Options Trading", "Portfolio Deployment"],
    },
    "🔬 Quant / Research Fund": {
        "description": "Full quantitative research and strategy tools",
        "base_plan":   "team",
        "enable":      ALL_MODULES,
        "disable":     [],
    },
    "🧪 Trial / Demo": {
        "description": "Limited trial — core features only, no trading",
        "base_plan":   "starter",
        "enable":      ["Screener", "Stock Dashboard", "Market Overview"],
        "disable":     ["Options Trading", "Portfolio", "Portfolio Construction",
                        "Portfolio Deployment", "Export / Sheets"],
    },
}


def _render_presets(db, user: dict):
    st.subheader("📦 Plan Presets")
    st.caption(
        "Apply a preset bundle to a tenant in one click. "
        "Presets set the base plan and configure module overrides automatically."
    )

    tenants = get_all_tenants(db)
    if not tenants:
        st.info("No tenants found.")
        return

    tenant_opts = {t["tenant_id"]: f"{t['tenant_id']} ({t['base_plan']})"
                   for t in tenants}
    sel_tid = st.selectbox(
        "Select Tenant",
        list(tenant_opts.keys()),
        format_func=lambda x: tenant_opts[x],
        key="preset_tenant",
    )

    st.markdown("---")

    for preset_name, preset in PRESETS.items():
        with st.container():
            col_info, col_apply = st.columns([4, 1])
            with col_info:
                plan_meta = PLAN_META.get(preset["base_plan"], PLAN_META["starter"])
                st.markdown(f"**{preset_name}**")
                st.caption(preset["description"])
                st.markdown(
                    f"Base plan: <span style='color:{plan_meta['color']}'>"
                    f"{plan_meta['emoji']} {plan_meta['name']}</span>"
                    + (f"  ·  +{len(preset['enable'])} modules enabled" if preset["enable"] else "")
                    + (f"  ·  -{len(preset['disable'])} modules disabled" if preset["disable"] else ""),
                    unsafe_allow_html=True,
                )
                with st.expander("View modules", expanded=False):
                    if preset["enable"]:
                        st.markdown("**Enabled:** " + ", ".join(preset["enable"]))
                    if preset["disable"]:
                        st.markdown("**Disabled:** " + ", ".join(preset["disable"]))
            with col_apply:
                st.write("")
                if st.button("Apply", key=f"preset_{preset_name}_{sel_tid}",
                              type="primary", use_container_width=True):
                    # Set base plan
                    set_tenant_plan(db, sel_tid, preset["base_plan"],
                                    custom_name=preset_name,
                                    updated_by=user.get("email"))
                    # Apply overrides
                    overrides = {m: True for m in preset["enable"]}
                    overrides.update({m: False for m in preset["disable"]})
                    if overrides:
                        set_bulk_module_overrides(db, sel_tid, overrides,
                                                   set_by=user.get("email"))
                    st.success(f"✅ Applied '{preset_name}' to {sel_tid}")
                    st.rerun()
        st.markdown("---")

    # Custom preset builder
    st.markdown("#### 🔧 Build Custom Preset")
    st.caption("Select modules to enable, then apply to a tenant.")

    sel_base = st.selectbox("Base plan", ["student","starter","pro","team"],
                             key="custom_preset_base")
    sel_modules = st.multiselect(
        "Enabled modules",
        ALL_MODULES,
        default=[m for m in ALL_MODULES
                 if PLAN_RANK.get(FEATURE_PLANS.get(m,"pro"),1) <=
                    PLAN_RANK.get(sel_base,1)],
        key="custom_preset_modules",
    )
    preset_label = st.text_input("Label", placeholder="My Custom Bundle",
                                  key="custom_preset_label")

    if st.button("Apply Custom Preset", type="primary", key="apply_custom_preset"):
        if sel_tid and sel_base:
            disabled = [m for m in ALL_MODULES if m not in sel_modules]
            set_tenant_plan(db, sel_tid, sel_base,
                            custom_name=preset_label or "Custom",
                            updated_by=user.get("email"))
            overrides = {m: True for m in sel_modules}
            overrides.update({m: False for m in disabled})
            set_bulk_module_overrides(db, sel_tid, overrides,
                                       set_by=user.get("email"))
            st.success(f"✅ Custom preset applied to {sel_tid}")
            st.rerun()


# ══════════════════════════════════════════════════════════════
# TAB 4 — AUDIT LOG
# ══════════════════════════════════════════════════════════════

def _render_audit(db):
    st.subheader("📋 Access Audit")
    st.caption("Current module access state for all tenants.")

    tenants = get_all_tenants(db)
    if not tenants:
        st.info("No tenants.")
        return

    rows = []
    for t in tenants:
        tid  = t["tenant_id"]
        plan = t["base_plan"]
        overrides = get_module_overrides(db, tid)

        for module in ALL_MODULES:
            req_plan    = FEATURE_PLANS.get(module, "pro")
            plan_allows = (PLAN_RANK.get(plan,1) >= PLAN_RANK.get(req_plan,1))
            final       = check_module_access(db, tid, module, plan_allows)
            is_override = module in overrides

            if is_override or True:  # show all
                rows.append({
                    "Tenant":     tid,
                    "Module":     module,
                    "Base Plan":  plan,
                    "Plan Allows":   "✅" if plan_allows else "❌",
                    "Override":      "🔵 ON" if (is_override and overrides[module]) else
                                     "🔴 OFF" if (is_override and not overrides[module]) else "—",
                    "Final Access":  "✅ Yes" if final else "❌ No",
                })

    if rows:
        df = pd.DataFrame(rows)

        # Filter controls
        col_t, col_m, col_s = st.columns(3)
        with col_t:
            tenant_filter = st.selectbox(
                "Filter tenant", ["All"] + [t["tenant_id"] for t in tenants],
                key="audit_tenant"
            )
        with col_m:
            access_filter = st.selectbox(
                "Filter access", ["All", "Has Access", "No Access", "Has Override"],
                key="audit_access"
            )
        with col_s:
            module_filter = st.selectbox(
                "Filter module", ["All"] + ALL_MODULES,
                key="audit_module"
            )

        filtered = df.copy()
        if tenant_filter != "All":
            filtered = filtered[filtered["Tenant"] == tenant_filter]
        if access_filter == "Has Access":
            filtered = filtered[filtered["Final Access"] == "✅ Yes"]
        elif access_filter == "No Access":
            filtered = filtered[filtered["Final Access"] == "❌ No"]
        elif access_filter == "Has Override":
            filtered = filtered[filtered["Override"] != "—"]
        if module_filter != "All":
            filtered = filtered[filtered["Module"] == module_filter]

        st.dataframe(filtered, use_container_width=True, hide_index=True,
                     height=500)

        csv = filtered.to_csv(index=False)
        st.download_button("⬇️ Export Audit CSV", csv,
                           "module_access_audit.csv", "text/csv")