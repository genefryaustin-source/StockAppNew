from modules.legal_portal import (
    DEFAULT_ESCALATION_POLICY,
    get_legal_workflow_runtime,
    run_escalations,
)


runtime = get_legal_workflow_runtime()


def recipient_resolver(acknowledgement, level):
    # Resolve a manager, tenant administrator, or super administrator.
    #
    # Return:
    #   (recipient_user_id, recipient_email)
    #
    # Return None when no valid escalation recipient exists.
    return None


sent = run_escalations(
    service=runtime.service,
    recipient_resolver=recipient_resolver,
    policy=DEFAULT_ESCALATION_POLICY,
    # notification_sink=email_legal_notification_sink,
    # sent_key_exists=notification_repository.exists,
    # record_sent_key=notification_repository.record,
)

print(f"Escalations sent: {sent}")
