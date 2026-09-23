from modules.legal_portal import (
    get_legal_workflow_runtime,
    principal_from_user,
    render_acknowledgement_banner,
    render_legal_persistence_status,
    render_legal_workflow_admin,
    render_user_acknowledgements,
)

# Preferred: pass the StockApp session factory.
#
# Example:
# from modules.db.core import SessionLocal
#
# legal_runtime = get_legal_workflow_runtime(
#     session_factory=SessionLocal,
# )

# Fallback: use DATABASE_URL directly.
legal_runtime = get_legal_workflow_runtime()

principal = principal_from_user(st.session_state.get("user"))

render_legal_persistence_status(
    principal=principal,
    runtime=legal_runtime,
)

render_acknowledgement_banner(
    principal=principal,
    service=legal_runtime.service,
)

# Navigation examples:
#
# elif selected_page == "Legal Acknowledgements":
#     render_user_acknowledgements(
#         principal=principal,
#         service=legal_runtime.service,
#     )
#
# elif selected_page == "Legal Review Workflow":
#     render_legal_workflow_admin(
#         principal=principal,
#         service=legal_runtime.service,
#     )
