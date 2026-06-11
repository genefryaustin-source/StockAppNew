import streamlit as st


def _section(title: str, body: str, expanded: bool = False) -> None:
    with st.expander(title, expanded=expanded):
        st.markdown(body)


def render_admin_help():
    st.title("🔐 Admin Help — Tenants, Users, Providers, Deployment")
    _section("Admin overview", """
Admin tools maintain the operational health of the platform: users, tenants, roles, providers, secrets, database health, analytics jobs, and deployment readiness.
""", True)
    _section("Tenant and user management", """
## Initial bootstrap
A new database requires at least:
- One tenant.
- One super admin user.
- One tenant admin user.

## Common roles
- `super_admin`: cross-tenant administration.
- `tenant_admin`: tenant-level administration.
- `client`: limited portfolio/client workflow.

## Common checks
```sql
SELECT id, name, is_active, created_at FROM tenants;
SELECT id, email, role, tenant_id, is_active, created_at FROM users;
```
""", True)
    _section("Provider and secrets management", """
Secrets should never be committed to Git. Configure them in Streamlit Cloud or local `.streamlit/secrets.toml`.

Common secrets include DATABASE_URL, market data keys, AI keys, transcript provider keys, and broker keys.
""")
    _section("Deployment checklist", """
1. Confirm `.gitignore` excludes secrets, local databases, caches, and virtual environments.
2. Run `git status` from project root.
3. Commit all required source files.
4. Push to GitHub.
5. Confirm Streamlit Cloud branch and secrets.
6. Verify database connection.
7. Verify tenants/users exist.
8. Confirm login.
9. Check provider health.
""")
    _section("Operational checks", """
Daily admin checks:
- App loads.
- Login works.
- Provider health is acceptable.
- Market data refresh succeeds.
- Analytics jobs complete.
- Cache errors are not present.
- Users have correct role access.
""")
    _section("Common admin failures", """
## Login succeeds but stays on login page
Check that `st.session_state['user']` is set and that the app reruns or stops correctly after login.

## AttributeError on user.get
The app continued past the auth gate with `user = None`.

## Duplicate widget ID
Login form rendered twice in the same Streamlit run.

## Empty users/tenants
Bootstrap or manual seed did not run.
""", True)

def render_help():
    render_admin_help()
