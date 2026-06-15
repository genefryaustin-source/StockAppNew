import pandas as pd
import streamlit as st

from sqlalchemy import text

from modules.auth.auth_service import (
    create_user,
    update_user,
    set_user_active,
    reset_user_password,
    delete_user,
)
from modules.auth.entitlements import get_all_plans, PLAN_META

from modules.admin.tenant_admin_ui import (
    render_tenant_admin_panel,
)

from modules.universe.universe_cleanup_ui import (
    render_universe_cleanup_ui,
)

from modules.ui.admin.provider_health_dashboard_page import (
    render_provider_health_dashboard_page,
)
from modules.admin.analytics_freshness_dashboard import (
    render_analytics_freshness_dashboard,
)
from modules.ui.admin.provider_operations_dashboard import (
    render_provider_operations_dashboard,
)

# ---------------------------------------------------------
# ACTIVE TENANT
# ---------------------------------------------------------
def get_active_tenant(user):

    if user.get("role") == "super_admin":
        return st.session_state.get("admin_selected_tenant")

    return user.get("tenant_id")


# ---------------------------------------------------------
# ADMIN PANEL
# ---------------------------------------------------------
def render_admin_panel(db, user):

    # ---------------------------------------------------------
    # FIX TENANT ID IF NAME STORED INSTEAD OF UUID
    # ---------------------------------------------------------
    if user.get("tenant_id") and not str(
        user.get("tenant_id")
    ).startswith((
        "a", "b", "c", "d", "e", "f",
        "0", "1", "2", "3", "4",
        "5", "6", "7", "8", "9",
    )):
        tenant_lookup = db.execute(text("""
            SELECT id
            FROM tenants
            WHERE name = :name
        """), {
            "name": user.get("tenant_id")
        }).fetchone()

        if tenant_lookup:
            user["tenant_id"] = tenant_lookup[0]
            st.session_state["user"]["tenant_id"] = tenant_lookup[0]

    role = user.get("role")
    tenant_id = user.get("tenant_id")

    st.title("Admin Console")

    # ---------------------------------------------------------
    # SUPER ADMIN TENANT SELECTOR
    # ---------------------------------------------------------
    if role == "super_admin":

        tenants = db.execute(text("""
            SELECT id, name
            FROM tenants
            ORDER BY name
        """)).fetchall()

        if not tenants:
            st.warning("No tenants found.")
            return

        tenant_map = {t[0]: t[1] for t in tenants}
        tenant_ids = list(tenant_map.keys())

        if (
            "admin_selected_tenant" not in st.session_state
            or not st.session_state["admin_selected_tenant"]
        ):
            st.session_state["admin_selected_tenant"] = tenant_ids[0]

        selected_tenant = st.selectbox(
            "Select Tenant",
            options=tenant_ids,
            format_func=lambda x: tenant_map[x],
            key="admin_selected_tenant",
        )

        tenant_id = selected_tenant

        st.success(f"Managing Tenant: {tenant_map[tenant_id]}")

    # ---------------------------------------------------------
    # MAIN TABS
    # ---------------------------------------------------------
    (
        tab_users,
        tab_plan,
        tab_tenants,
        tab_cleanup,
        provider_health_tab,
        provider_operations_tab,
        analytics_freshness_tab,

    ) = st.tabs([
        "👤 Users",
        "💳 Plan Management",
        "🏢 Tenants",
        "🧹 Universe Cleanup",
        "🔌 Provider Health",
        "🚀 Provider Operations",
        "📊 Universe Analytics",
    ])

    # =========================================================
    # USERS TAB
    # =========================================================
    with tab_users:

        allowed_roles = (
            ["client", "tenant_admin"]
            if role == "tenant_admin"
            else ["client", "tenant_admin", "super_admin"]
        )

        # ---------------------------------------------------------
        # CREATE USER
        # ---------------------------------------------------------
        st.subheader("Create User")

        c1, c2 = st.columns(2)

        new_email = c1.text_input(
            "Email",
            key="admin_new_email",
        )
        new_password = c2.text_input(
            "Password",
            type="password",
            key="admin_new_password",
        )

        new_role = st.selectbox(
            "Role",
            allowed_roles,
            key="admin_new_role",
        )

        c3, c4 = st.columns(2)
        new_plan = c3.selectbox(
            "Plan",
            get_all_plans(),
            index=1,  # default to starter
            key="admin_new_plan",
            format_func=lambda p: f"{PLAN_META[p]['emoji']} {PLAN_META[p]['name']} — {PLAN_META[p]['price']}",
        )

        if role == "super_admin":
            new_tenant_id = c4.text_input(
                "Tenant ID",
                value=tenant_id or "",
                key="admin_new_tenant",
            )
        else:
            new_tenant_id = tenant_id

        if st.button("Create User", key="admin_create_user"):
            if not new_email or not new_password:
                st.warning("Email and password are required.")
            else:
                try:
                    create_user(
                        db=db,
                        email=new_email,
                        password=new_password,
                        role=new_role,
                        tenant_id=new_tenant_id,
                        is_active=True,
                    )

                    from sqlalchemy import text as _text

                    db.execute(
                        _text(
                            """
                            UPDATE users
                            SET plan = :plan
                            WHERE email = :email
                            """
                        ),
                        {
                            "plan": new_plan,
                            "email": new_email.lower().strip(),
                        },
                    )

                    db.commit()

                    st.success(
                        f"User created with {PLAN_META[new_plan]['name']} plan."
                    )

                    st.rerun()

                except Exception as e:
                    db.rollback()
                    st.error(f"Create failed: {e}")
        # ---------------------------------------------------------
        # USER LIST
        # ---------------------------------------------------------

        if role == "super_admin":

            rows = db.execute(text("""
                SELECT *
                FROM users
                WHERE tenant_id = :tenant
                ORDER BY email
            """), {
                "tenant": tenant_id
            }).fetchall()

        else:

            rows = db.execute(text("""
                SELECT *
                FROM users
                WHERE tenant_id = :tenant
                  AND role <> 'super_admin'
                ORDER BY email
            """), {
                "tenant": tenant_id
            }).fetchall()

        if not rows:
            st.info("No users found.")
        else:
            df = pd.DataFrame([dict(r._mapping) for r in rows])

            st.dataframe(
                df.copy(),
                use_container_width=True,
                hide_index=True,
            )

            # ---------------------------------------------------------
            # USER MANAGEMENT
            # ---------------------------------------------------------
            st.divider()
            st.subheader("Manage User")

            user_options = {
                f"{r.email} | {r.role} | {r.id}": r.id
                for r in rows
            }

            selected_label = st.selectbox(
                "Select User",
                list(user_options.keys()),
                key="admin_selected_user",
            )

            selected_user_id = user_options[selected_label]
            selected_row = df[df["id"] == selected_user_id].iloc[0]

            e1, e2 = st.columns(2)

            edit_email = e1.text_input(
                "Edit Email",
                value=selected_row["email"],
                key="admin_edit_email",
            )
            edit_role = e2.selectbox(
                "Edit Role",
                allowed_roles,
                index=max(
                    0,
                    allowed_roles.index(selected_row["role"])
                ) if selected_row["role"] in allowed_roles else 0,
                key="admin_edit_role",
            )

            if role == "super_admin":
                edit_tenant_id = st.text_input(
                    "Edit Tenant ID",
                    value="" if pd.isna(
                        selected_row.get("tenant_id")
                    ) else str(selected_row.get("tenant_id")),
                    key="admin_edit_tenant",
                )
            else:
                edit_tenant_id = tenant_id

            # Plan selector for existing user
            current_plan = str(selected_row.get("plan") or "starter")
            if current_plan not in get_all_plans():
                current_plan = "starter"
            edit_plan = st.selectbox(
                "Plan",
                get_all_plans(),
                index=get_all_plans().index(current_plan),
                key="admin_edit_plan",
                format_func=lambda p: f"{PLAN_META[p]['emoji']} {PLAN_META[p]['name']} — {PLAN_META[p]['price']}",
            )

            a1, a2, a3, a4 = st.columns(4)

            # ---------------------------------------------------------
            # SAVE USER
            # ---------------------------------------------------------
            if a1.button("Save Changes", key="admin_save_user"):
                try:
                    update_user(
                        db=db,
                        target_user_id=selected_user_id,
                        email=edit_email,
                        role=edit_role,
                        tenant_id=edit_tenant_id,
                    )
                    # Update plan
                    from sqlalchemy import text as _text
                    db.execute(_text(
                        "UPDATE users SET plan = :plan WHERE id = :uid"
                    ), {"plan": edit_plan, "uid": selected_user_id})
                    db.commit()
                    st.success(f"User updated — plan set to {PLAN_META[edit_plan]['name']}.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Update failed: {e}")

            # ---------------------------------------------------------
            # TOGGLE ACTIVE
            # ---------------------------------------------------------
            is_active = bool(selected_row["is_active"])
            toggle_label = "Deactivate User" if is_active else "Reactivate User"

            if a2.button(toggle_label, key="admin_toggle_user"):
                try:
                    set_user_active(db, selected_user_id, not is_active)
                    st.success("User status updated.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Status change failed: {e}")

            # ---------------------------------------------------------
            # RESET PASSWORD
            # ---------------------------------------------------------
            new_reset_password = st.text_input(
                "Reset Password",
                type="password",
                key="admin_reset_password",
            )

            if a3.button("Reset Password", key="admin_reset_user_pw"):
                if not new_reset_password:
                    st.warning("Enter a new password first.")
                else:
                    try:
                        reset_user_password(
                            db, selected_user_id, new_reset_password
                        )
                        st.success("Password reset.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Password reset failed: {e}")

            # ---------------------------------------------------------
            # DELETE USER
            # ---------------------------------------------------------
            if a4.button("Delete User", key="admin_delete_user"):
                try:
                    if selected_user_id == user.get("user_id"):
                        st.error(
                            "You cannot delete your own logged-in account."
                        )
                    else:
                        delete_user(db, selected_user_id)
                        st.success("User deleted.")
                        st.rerun()
                except Exception as e:
                    st.error(f"Delete failed: {e}")

    # =========================================================
    # PLAN MANAGEMENT TAB
    # =========================================================
    with tab_plan:

        _render_plan_management_tab(db, user, tenant_id)

    # =========================================================
    # TENANTS TAB
    # =========================================================
    with tab_tenants:

        if role == "super_admin":
            tenant_id = st.session_state.get("admin_selected_tenant")
        else:
            tenant_id = user.get("tenant_id")

        if not tenant_id:
            st.error("❌ No tenant context available")
        else:
            render_tenant_admin_panel(
                db,
                {**user, "tenant_id": tenant_id},
            )

    # =========================================================
    # UNIVERSE CLEANUP TAB
    # =========================================================
    with tab_cleanup:

        try:
            render_universe_cleanup_ui(db)
        except Exception as e:
            st.error(f"Universe cleanup failed: {e}")

    # =========================================================
    # PROVIDER HEALTH TAB
    # =========================================================
    with provider_health_tab:

        render_provider_health_dashboard_page(
            db=db,
            user=user,
        )

    # =========================================================
    # PROVIDER OPERATIONS TAB
    # =========================================================

    with provider_operations_tab:

        render_provider_operations_dashboard(
            db=db,
            user=user,
        )

    with analytics_freshness_tab:

        render_analytics_freshness_dashboard(
            db=db,
            user=user,
        )

# ─────────────────────────────────────────────────────────────
# Plan Management Tab — inline within admin_ui
# ─────────────────────────────────────────────────────────────

def _render_plan_management_tab(db, user, tenant_id):
    """
    Super admin plan management — set plans for users and tenants
    with one-click SQL execution. No NeonDB console needed.
    """
    from sqlalchemy import text
    from modules.auth.entitlements import get_all_plans, PLAN_META, PLAN_RANK

    role = user.get("role")

    st.subheader("💳 Plan Management")
    st.caption(
        "Set plans for individual users or entire tenants. "
        "Changes take effect immediately on next page load."
    )

    # ── Sub-tabs ──────────────────────────────────────────────
    pt1, pt2, pt3 = st.tabs([
        "👤 Set User Plan",
        "🏢 Set Tenant Plan",
        "📊 Plan Overview",
    ])

    # ── Tab 1: Set individual user plan ──────────────────────
    with pt1:
        st.markdown("#### Set Plan for a Specific User")
        st.caption("Select a user and assign them a plan with one click.")

        try:
            if role == "super_admin":
                rows = db.execute(text("""
                    SELECT id, email, role, tenant_id,
                           COALESCE(plan, 'starter') as plan
                    FROM users
                    ORDER BY tenant_id, email
                """)).fetchall()
            else:
                rows = db.execute(text("""
                    SELECT id, email, role, tenant_id,
                           COALESCE(plan, 'starter') as plan
                    FROM users
                    WHERE tenant_id = :tid
                    ORDER BY email
                """), {"tid": tenant_id}).fetchall()

            if not rows:
                st.info("No users found.")
                return

            # User selector
            user_opts = {
                f"{r[1]} ({r[2]}) — {PLAN_META.get(r[4], {}).get('emoji','🥉')} {r[4]}": r[0]
                for r in rows
            }
            sel_label = st.selectbox(
                "Select User",
                list(user_opts.keys()),
                key="pm_user_sel",
            )
            sel_uid = user_opts[sel_label]
            sel_row = next(r for r in rows if r[0] == sel_uid)
            current_plan = str(sel_row[4] or "starter")

            col_plan, col_btn = st.columns([3, 1])
            with col_plan:
                new_plan = st.selectbox(
                    "New Plan",
                    get_all_plans(),
                    index=get_all_plans().index(current_plan)
                          if current_plan in get_all_plans() else 1,
                    key="pm_new_plan",
                    format_func=lambda p: (
                        f"{PLAN_META[p]['emoji']} {PLAN_META[p]['name']} "
                        f"— {PLAN_META[p]['price']}"
                    ),
                )
            with col_btn:
                st.write("")
                if st.button(
                    "✅ Apply Plan",
                    key="pm_apply_user",
                    type="primary",
                    use_container_width=True,
                ):
                    try:
                        db.rollback()
                    except Exception:
                        pass
                    try:
                        db.execute(text(
                            "UPDATE users SET plan = :plan WHERE id = :uid"
                        ), {"plan": new_plan, "uid": sel_uid})
                        db.commit()
                        meta = PLAN_META[new_plan]
                        st.success(
                            f"✅ **{sel_row[1]}** → "
                            f"{meta['emoji']} **{meta['name']}** ({meta['price']})"
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")

            # Show the SQL that was executed
            with st.expander("🔍 SQL executed", expanded=False):
                st.code(
                    f"UPDATE users SET plan = '{new_plan}' "
                    f"WHERE id = '{sel_uid}';  -- {sel_row[1]}",
                    language="sql",
                )

        except Exception as e:
            st.error(f"Failed to load users: {e}")

    # ── Tab 2: Set entire tenant plan ─────────────────────────
    with pt2:
        st.markdown("#### Set Plan for All Users in a Tenant")
        st.caption(
            "Updates every user in the selected tenant to the same plan. "
            "Useful for onboarding a new client or upgrading a whole team."
        )

        try:
            # Get distinct tenants
            tenant_rows = db.execute(text("""
                SELECT DISTINCT u.tenant_id,
                       COALESCE(t.name, u.tenant_id) as tenant_name,
                       COUNT(u.id) as user_count
                FROM users u
                LEFT JOIN tenants t ON u.tenant_id = t.id
                WHERE u.tenant_id IS NOT NULL
                GROUP BY u.tenant_id, t.name
                ORDER BY tenant_name
            """)).fetchall()

            if not tenant_rows:
                st.info("No tenants found.")
                return

            t_opts = {
                f"{r[1]} ({r[2]} users)": r[0]
                for r in tenant_rows
            }
            sel_tenant_label = st.selectbox(
                "Select Tenant",
                list(t_opts.keys()),
                key="pm_tenant_sel",
            )
            sel_tenant_id = t_opts[sel_tenant_label]

            col_tp, col_tb = st.columns([3, 1])
            with col_tp:
                tenant_plan = st.selectbox(
                    "Plan for all users",
                    get_all_plans(),
                    index=1,
                    key="pm_tenant_plan",
                    format_func=lambda p: (
                        f"{PLAN_META[p]['emoji']} {PLAN_META[p]['name']} "
                        f"— {PLAN_META[p]['price']}"
                    ),
                )
            with col_tb:
                st.write("")
                if st.button(
                    "✅ Apply to All",
                    key="pm_apply_tenant",
                    type="primary",
                    use_container_width=True,
                ):
                    try:
                        db.rollback()
                    except Exception:
                        pass
                    try:
                        result = db.execute(text("""
                            UPDATE users
                            SET plan = :plan
                            WHERE tenant_id = :tid
                        """), {"plan": tenant_plan, "tid": sel_tenant_id})
                        db.commit()
                        meta  = PLAN_META[tenant_plan]
                        count = result.rowcount
                        st.success(
                            f"✅ **{count} users** in tenant updated to "
                            f"{meta['emoji']} **{meta['name']}**"
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")

            with st.expander("🔍 SQL executed", expanded=False):
                st.code(
                    f"UPDATE users SET plan = '{tenant_plan}' "
                    f"WHERE tenant_id = '{sel_tenant_id}';",
                    language="sql",
                )

        except Exception as e:
            st.error(f"Failed to load tenants: {e}")

    # ── Tab 3: Plan overview ──────────────────────────────────
    with pt3:
        st.markdown("#### Current Plan Distribution")
        st.caption("All users and their assigned plans.")

        try:
            all_rows = db.execute(text("""
                SELECT u.email, u.role,
                       COALESCE(t.name, u.tenant_id) as tenant,
                       COALESCE(u.plan, 'starter') as plan,
                       u.is_active
                FROM users u
                LEFT JOIN tenants t ON u.tenant_id = t.id
                ORDER BY u.tenant_id, u.email
            """)).fetchall()

            if not all_rows:
                st.info("No users found.")
                return

            import pandas as pd
            df = pd.DataFrame(all_rows, columns=["Email","Role","Tenant","Plan","Active"])
            df["Plan Label"] = df["Plan"].apply(
                lambda p: f"{PLAN_META.get(p,{}).get('emoji','?')} {p.title()}"
            )
            df["Active"] = df["Active"].apply(lambda x: "✅" if x else "❌")

            # Summary metrics
            plans = df["Plan"].tolist()
            c1,c2,c3,c4,c5 = st.columns(5)
            c1.metric("Total Users",   len(df))
            c2.metric("🎓 Student",    plans.count("student"))
            c3.metric("🥉 Starter",    plans.count("starter"))
            c4.metric("🥈 Pro",        plans.count("pro"))
            c5.metric("🥇 Team",       plans.count("team"))

            st.dataframe(
                df[["Email","Role","Tenant","Plan Label","Active"]],
                use_container_width=True,
                hide_index=True,
            )

            # CSV export
            csv = df.to_csv(index=False)
            st.download_button(
                "⬇️ Export Plan Report CSV",
                csv,
                "plan_report.csv",
                "text/csv",
                key="pm_export_csv",
            )

            # Quick bulk operations
            st.markdown("#### ⚡ Quick Bulk Operations")
            col_op, col_run = st.columns([3, 1])
            with col_op:
                bulk_op = st.selectbox(
                    "Operation",
                    [
                        "Set ALL users without a plan to Starter",
                        "Set ALL Student users to Starter",
                        "Set ALL Starter users to Pro",
                        "Set ALL Pro users to Team",
                    ],
                    key="pm_bulk_op",
                )
            with col_run:
                st.write("")
                if st.button(
                    "▶ Run",
                    key="pm_bulk_run",
                    type="secondary",
                    use_container_width=True,
                ):
                    try:
                        db.rollback()
                    except Exception:
                        pass
                    sql_map = {
                        "Set ALL users without a plan to Starter":
                            "UPDATE users SET plan = 'starter' WHERE plan IS NULL",
                        "Set ALL Student users to Starter":
                            "UPDATE users SET plan = 'starter' WHERE plan = 'student'",
                        "Set ALL Starter users to Pro":
                            "UPDATE users SET plan = 'pro' WHERE plan = 'starter'",
                        "Set ALL Pro users to Team":
                            "UPDATE users SET plan = 'team' WHERE plan = 'pro'",
                    }
                    sql = sql_map[bulk_op]
                    try:
                        result = db.execute(text(sql))
                        db.commit()
                        st.success(f"✅ {result.rowcount} users updated.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")

        except Exception as e:
            st.error(f"Failed to load plan overview: {e}")

