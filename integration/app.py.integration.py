# Add near the other app.py imports:
from modules.legal_portal import (
    render_application_legal_footer,
    render_legal_admin_dashboard,
    render_legal_portal,
    resolve_legal_route,
    principal_from_user,
)


# IMPORTANT:
# Place this public route check AFTER st.set_page_config() and essential
# startup initialization, but BEFORE the authentication gate/login render.

legal_route = resolve_legal_route()

if legal_route.active:
    render_legal_portal(
        default_document=legal_route.document_key,
        current_user=st.session_state.get("user"),
        # audit_sink=your_existing_audit_sink,  # optional
    )
    st.stop()


# Add an authenticated navigation branch where your application chooses pages:
#
# elif selected_page == "Legal Portal":
#     render_legal_portal(current_user=st.session_state.get("user"))
#
# elif selected_page == "Legal Portal Operations":
#     principal = principal_from_user(st.session_state.get("user"))
#     render_legal_admin_dashboard(principal)


# Add once at the bottom of authenticated application rendering:
render_application_legal_footer(
    build_version=None,  # replace with your application version
    git_commit=None,     # replace with your build commit if available
)
