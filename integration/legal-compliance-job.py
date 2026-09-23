from modules.legal_portal import (
    get_legal_workflow_runtime,
    run_legal_compliance_job,
)


runtime = get_legal_workflow_runtime()

result = run_legal_compliance_job(
    service=runtime.service,
    # user_email_resolver=resolve_user_email,
    # notification_sink=email_legal_notification_sink,
)

print(
    f"Assignments={result.total_assignments} "
    f"Overdue={result.overdue_assignments} "
    f"Notifications={result.notifications_sent}"
)
