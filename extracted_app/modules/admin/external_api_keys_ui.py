"""
modules/admin/external_api_keys_ui.py

"External API Access" admin tab -- manages api.auth.api_keys
PlatformAPIKey records: the INBOUND credentials external systems and
integration partners present to call this platform's own REST API
(POST /api/v1/orders, GET /api/v1/portfolio, etc.).

Not to be confused with modules/admin/api_keys_ui.py's "🔑 API Keys"
tab, which manages the OPPOSITE direction -- a tenant's own OUTBOUND
credentials for third-party providers (Polygon, OpenAI, ...). Different
table (platform_api_keys vs tenant_api_keys), different direction,
different purpose. The similar names are a genuine, pre-existing source
of confusion in this codebase, not a naming choice made here -- this
tab is deliberately labeled "External API Access" rather than
"API Keys" again to keep the two visually distinct in the tab bar.

Two views in one tab:

  Tenant self-service
      Full lifecycle (create, view, edit, rotate, revoke) for whichever
      tenant is currently active -- same tenant selector convention as
      api_keys_ui.py's _active_tenant_id().

  Super-admin oversight (role == "super_admin" only)
      Every key across every tenant in one place, with the same
      lifecycle actions available cross-tenant, plus creating a key on
      behalf of any tenant. This is also where a rate limit gets
      lowered or a key gets revoked in response to suspected abuse --
      the operator-facing half of DDoS mitigation. The enforcement
      itself happens in api/middleware/rate_limit.py, which reads the
      same rate_limit_per_minute value this UI edits; this tab doesn't
      show live in-progress request counts, since those live in that
      middleware's in-memory, per-process state, not the database --
      what's shown here (created_at, last_used_at, status) is
      everything the database actually knows about a key.
"""

from __future__ import annotations

import json
from datetime import datetime, time as dtime, UTC

import streamlit as st

from api.auth.api_keys import api_key_service
from api.auth.permissions import PERMISSIONS


# ==============================================================
# Helpers
# ==============================================================

def _active_tenant_id(user) -> str | None:
    if user.get("role") == "super_admin":
        return st.session_state.get("admin_selected_tenant")
    return user.get("tenant_id")


def _fmt_dt(value) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if value else "—"


def _parse_permissions(record) -> list[str]:
    try:
        return json.loads(record.permissions or "[]")
    except (TypeError, ValueError):
        return []


def _is_revoked(record) -> bool:
    return record.revoked_at is not None or not record.is_active


def _is_expired(record) -> bool:
    if record.expires_at is None:
        return False
    now = datetime.now(UTC).replace(tzinfo=record.expires_at.tzinfo)
    return record.expires_at < now


def _status_badge(record) -> str:
    if _is_revoked(record):
        return "🔴 Revoked"
    if _is_expired(record):
        return "🟠 Expired"
    return "🟢 Active"


# ==============================================================
# Create form (shared by both self-service and admin views)
# ==============================================================

def _create_key_form(db, *, tenant_id: str | None, user, form_key: str, allow_tenant_override: bool = False):
    with st.form(form_key, clear_on_submit=True):

        name = st.text_input(
            "Key name", placeholder="e.g. Acme Corp Trading Integration",
        )

        target_tenant = tenant_id
        if allow_tenant_override:
            target_tenant = st.text_input(
                "Tenant ID",
                value=tenant_id or "",
                help="Which tenant this key belongs to. Defaults to the currently selected tenant -- change this to onboard a different company that doesn't have any keys yet.",
            )

        permissions = st.multiselect(
            "Permissions",
            options=sorted(PERMISSIONS),
            help="What this key is allowed to do. A key with no permissions selected can authenticate but can't call anything.",
        )

        c1, c2 = st.columns(2)

        rate_limit = c1.number_input(
            "Rate limit (requests/minute)",
            min_value=1, max_value=10000, value=100,
            help="Enforced by the API's rate-limit middleware. Start lower for a key you don't fully trust yet, or for a new/unproven integration.",
        )

        has_expiration = c2.checkbox("Set an expiration date")
        expires_at = None
        if has_expiration:
            exp_date = c2.date_input("Expires on")
            expires_at = datetime.combine(exp_date, dtime(23, 59, 59))

        submitted = st.form_submit_button("Create key", type="primary")

        if not submitted:
            return

        if not name.strip():
            st.error("Key name is required.")
            return

        if not target_tenant:
            st.error("Tenant ID is required.")
            return

        raw_key, record, error_reason = api_key_service.create_key(
            db,
            tenant_id=target_tenant.strip(),
            name=name.strip(),
            permissions=permissions,
            rate_limit_per_minute=int(rate_limit),
            expires_at=expires_at,
            created_by_user_id=str(user.get("user_id") or ""),
        )

        if record is None:
            st.error(error_reason or "Something went wrong creating the key. Nothing was saved.")
            return

        st.session_state["_just_created_api_key"] = {
            "raw_key": raw_key,
            "name": record.name,
            "id": record.id,
            "tenant_id": record.tenant_id,
        }
        st.rerun()


def _show_just_created_banner():
    """
    One-time display of a freshly created or rotated raw key. Popped
    from session_state immediately, so a rerun (or navigating away and
    back) never shows it a second time -- the raw key genuinely cannot
    be retrieved after this point, by design; only its hash is stored.
    """

    created = st.session_state.pop("_just_created_api_key", None)
    if not created:
        return

    st.success(f"✅ Key **{created['name']}** ready for tenant `{created['tenant_id']}`.")
    st.warning(
        "**Copy this key now — it will not be shown again.** Only a masked "
        "version is stored. If it's lost, the only options are rotating this "
        "key (issues a new secret, same key record) or creating a new one."
    )
    st.code(created["raw_key"], language=None)


# ==============================================================
# Per-key summary + actions
# ==============================================================

def _render_key_summary_row(record, *, show_tenant: bool):
    perms = _parse_permissions(record)

    c1, c2, c3 = st.columns([3, 3, 2])

    with c1:
        st.markdown(f"**{record.name}**")
        st.caption(f"`{record.key_prefix}_...{record.key_suffix}`")
        if show_tenant:
            st.caption(f"tenant: `{record.tenant_id}`")

    with c2:
        st.write(_status_badge(record))
        st.caption(
            ", ".join(f"`{p}`" for p in perms) if perms else "_no permissions_"
        )
        st.caption(f"limit: {record.rate_limit_per_minute}/min")

    with c3:
        st.caption(f"created {_fmt_dt(record.created_at)}")
        st.caption(f"last used {_fmt_dt(record.last_used_at)}")
        if record.expires_at:
            st.caption(f"expires {_fmt_dt(record.expires_at)}")
        if record.revoked_at:
            st.caption(f"revoked {_fmt_dt(record.revoked_at)}")


def _key_row_actions(db, record, *, is_admin: bool, action_prefix: str):
    """
    Edit / rotate / revoke actions for one key. Scoped to
    record.tenant_id when not is_admin, so tenant self-service can
    never act on another tenant's key -- enforced again here even
    though api_key_service already enforces it server-side, so a bug
    in this UI fails closed rather than open.
    """

    if _is_revoked(record):
        # A revoked key's history stays visible (see api_key_service.get_key's
        # docstring), but there's nothing left to do to it.
        return

    scope_tenant = None if is_admin else record.tenant_id

    with st.expander(f"⚙️ Manage \"{record.name}\""):

        with st.form(f"{action_prefix}_edit_{record.id}"):

            new_name = st.text_input("Name", value=record.name)

            new_permissions = st.multiselect(
                "Permissions",
                options=sorted(PERMISSIONS),
                default=_parse_permissions(record),
            )

            new_rate_limit = st.number_input(
                "Rate limit (requests/minute)",
                min_value=1, max_value=10000,
                value=int(record.rate_limit_per_minute),
            )

            clear_expiration = False
            new_expires_at = record.expires_at
            if record.expires_at:
                clear_expiration = st.checkbox(
                    f"Clear expiration (currently {_fmt_dt(record.expires_at)})",
                )

            save = st.form_submit_button("💾 Save changes")

            if save:
                updated = api_key_service.update_key(
                    db,
                    key_id=record.id,
                    tenant_id=scope_tenant,
                    name=new_name.strip() or record.name,
                    permissions=new_permissions,
                    rate_limit_per_minute=int(new_rate_limit),
                    clear_expiration=clear_expiration,
                )
                if updated is None:
                    st.error("Could not update this key.")
                else:
                    st.success("Updated.")
                    st.rerun()

        rc1, rc2 = st.columns(2)

        with rc1:
            confirm_rotate = st.checkbox(
                "Confirm rotate", key=f"{action_prefix}_confirm_rotate_{record.id}",
            )
            if st.button(
                "🔄 Rotate secret",
                key=f"{action_prefix}_rotate_{record.id}",
                disabled=not confirm_rotate,
                use_container_width=True,
            ):
                raw_key, updated = api_key_service.rotate_key(
                    db, key_id=record.id, tenant_id=scope_tenant,
                )
                if updated is None:
                    st.error("Could not rotate this key.")
                else:
                    st.session_state["_just_created_api_key"] = {
                        "raw_key": raw_key,
                        "name": updated.name,
                        "id": updated.id,
                        "tenant_id": updated.tenant_id,
                    }
                    st.rerun()

        with rc2:
            confirm_revoke = st.checkbox(
                "Confirm revoke", key=f"{action_prefix}_confirm_revoke_{record.id}",
            )
            if st.button(
                "🗑️ Revoke",
                key=f"{action_prefix}_revoke_{record.id}",
                disabled=not confirm_revoke,
                type="primary",
                use_container_width=True,
            ):
                ok = api_key_service.revoke_key(
                    db, key_id=record.id, tenant_id=scope_tenant,
                )
                if ok:
                    st.success(f"Revoked \"{record.name}\".")
                    st.rerun()
                else:
                    st.error("Could not revoke this key.")


# ==============================================================
# Main entry point
# ==============================================================

def render_external_api_keys_tab(db, user):

    st.subheader("🌐 External API Access")
    st.caption(
        "API keys that external systems and integration partners use to "
        "authenticate against this platform's own REST API. Not the same as "
        "the 🔑 API Keys tab, which manages this tenant's own outbound "
        "provider credentials (Polygon, OpenAI, etc.)."
    )

    _show_just_created_banner()

    role = user.get("role")
    if role not in ("tenant_admin", "super_admin"):
        st.info("Only tenant admins and super admins can manage external API keys.")
        return

    tenant_id = _active_tenant_id(user)

    # ---------------------------------------------------------
    # Tenant self-service
    # ---------------------------------------------------------
    if not tenant_id:
        st.warning("No active tenant context.")
    else:
        # Effective access (accounts for the development-mode exemption
        # in api_key_service), not the raw stored flag -- otherwise this
        # banner would say "blocked" in dev mode even though creating a
        # key would actually succeed there.
        has_access = api_key_service.has_platform_api_access(db, tenant_id)

        st.markdown(f"#### Your tenant's API keys — `{tenant_id}`")

        if not has_access:
            st.warning(
                "🚫 External platform API access is not enabled for this "
                "tenant. Only a super admin can turn this on, from the 🏢 "
                "Tenants tab or the platform-wide oversight section below. "
                "No new keys can be created until then."
            )

        with st.expander("➕ Create a new key"):
            _create_key_form(
                db, tenant_id=tenant_id, user=user, form_key="tenant_create_key_form",
            )

        keys = api_key_service.list_keys(db, tenant_id=tenant_id)

        if not keys:
            st.info("No API keys yet for this tenant.")
        else:
            active_n = sum(1 for k in keys if not _is_revoked(k))
            st.caption(f"{active_n} active, {len(keys) - active_n} revoked")

            for record in keys:
                st.divider()
                _render_key_summary_row(record, show_tenant=False)
                _key_row_actions(db, record, is_admin=False, action_prefix="tenant")

    # ---------------------------------------------------------
    # Super-admin oversight
    # ---------------------------------------------------------
    if role == "super_admin":

        st.divider()
        st.markdown("### 🛡️ Platform-wide oversight (all tenants)")
        st.caption(
            "Every API key on the platform, across every tenant. Use this to spot "
            "abuse -- a key that's never been used, unusually heavy traffic from "
            "one integration -- and to lower a key's rate limit or revoke it "
            "outright if you suspect it's being used to attack the API."
        )

        all_keys = api_key_service.list_keys(db, tenant_id=None)

        active_count = sum(1 for k in all_keys if not _is_revoked(k))
        revoked_count = len(all_keys) - active_count
        never_used = sum(
            1 for k in all_keys if not _is_revoked(k) and k.last_used_at is None
        )
        tenant_count = len({k.tenant_id for k in all_keys})

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Active keys", active_count)
        m2.metric("Revoked keys", revoked_count)
        m3.metric("Never used", never_used)
        m4.metric("Tenants with keys", tenant_count)

        with st.expander("➕ Create a key on behalf of any tenant"):
            _create_key_form(
                db, tenant_id=tenant_id, user=user,
                form_key="admin_create_key_form", allow_tenant_override=True,
            )

        f1, f2 = st.columns([2, 2])

        tenant_filter = f1.text_input(
            "Filter by tenant ID (blank = all)", key="admin_key_tenant_filter",
        )

        sort_choice = f2.selectbox(
            "Sort by",
            ["Most recently created", "Most recently used", "Least recently used"],
            key="admin_key_sort",
        )

        if tenant_filter.strip():
            from modules.admin.tenant_service import TenantService

            filtered_tenant = tenant_filter.strip()
            tenant_svc = TenantService(db)
            filtered_has_access = tenant_svc.get_platform_api_access(filtered_tenant)

            gc1, gc2 = st.columns([3, 1])
            gc1.caption(
                f"🌐 External API access for `{filtered_tenant}` is currently "
                + ("**enabled**." if filtered_has_access else "**disabled**.")
            )
            if filtered_has_access:
                if gc2.button("Revoke access", key="admin_gate_revoke"):
                    if tenant_svc.set_platform_api_access(filtered_tenant, False):
                        st.success(
                            f"Revoked API access for `{filtered_tenant}`. Its "
                            "existing keys will stop working immediately."
                        )
                        st.rerun()
                    else:
                        st.error("Failed to revoke API access (tenant not found?).")
            else:
                if gc2.button("Grant access", key="admin_gate_grant"):
                    if tenant_svc.set_platform_api_access(filtered_tenant, True):
                        st.success(f"Granted API access to `{filtered_tenant}`.")
                        st.rerun()
                    else:
                        st.error("Failed to grant API access (tenant not found?).")

        visible_keys = [
            k for k in all_keys
            if not tenant_filter.strip() or k.tenant_id == tenant_filter.strip()
        ]

        epoch = datetime(1970, 1, 1, tzinfo=UTC)

        def _sort_val(k, field):
            v = getattr(k, field)
            if v is None:
                return epoch
            return v if v.tzinfo else v.replace(tzinfo=UTC)

        if sort_choice == "Most recently created":
            visible_keys.sort(key=lambda k: _sort_val(k, "created_at"), reverse=True)
        elif sort_choice == "Most recently used":
            visible_keys.sort(key=lambda k: _sort_val(k, "last_used_at"), reverse=True)
        else:
            visible_keys.sort(key=lambda k: _sort_val(k, "last_used_at"))

        if not visible_keys:
            st.info("No keys match this filter.")
        else:
            for record in visible_keys:
                st.divider()
                _render_key_summary_row(record, show_tenant=True)
                _key_row_actions(db, record, is_admin=True, action_prefix="admin")