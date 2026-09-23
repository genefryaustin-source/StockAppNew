from modules.legal_portal import (
    build_legal_operations_runtime,
    get_legal_workflow_runtime,
    principal_from_user,
    render_legal_operations_dashboard,
    render_legal_recovery_dashboard,
)

# Replace with the StockApp SQLAlchemy session factory:
# from modules.db.core import SessionLocal

workflow_runtime = get_legal_workflow_runtime(
    # session_factory=SessionLocal,
)

operations_runtime = build_legal_operations_runtime(
    # session_factory=SessionLocal,
    # delivery_sink=email_legal_notification_sink,
)

principal = principal_from_user(st.session_state.get("user"))

# Navigation examples:
#
# elif selected_page == "Legal Operations Control":
#     render_legal_operations_dashboard(
#         principal=principal,
#         workflow_service=workflow_runtime.service,
#         override_service=operations_runtime.override_service,
#     )
#
# elif selected_page == "Legal Backup & Recovery":
#     render_legal_recovery_dashboard(
#         principal=principal,
#         service=workflow_runtime.service,
#     )
