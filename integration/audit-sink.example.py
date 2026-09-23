from modules.legal_portal import LegalAuditEvent


def stockapp_legal_audit_sink(event: LegalAuditEvent) -> None:
    # Adapt this function to your existing audit repository/service.
    #
    # Example:
    #
    # audit_service.record(
    #     event_type=event.event_type,
    #     actor_user_id=event.user_id,
    #     tenant_id=event.tenant_id,
    #     resource_type="legal_document",
    #     resource_id=event.document_key,
    #     metadata=dict(event.metadata),
    #     occurred_at=event.occurred_at,
    # )
    pass
