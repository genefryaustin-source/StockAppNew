from modules.legal_portal import LegalNotification


def email_legal_notification_sink(
    notification: LegalNotification,
) -> None:
    # Connect this function to the existing StockApp email provider.
    #
    # Example:
    #
    # email_service.send(
    #     to=notification.recipient_email,
    #     subject=notification.subject,
    #     body=notification.message,
    # )
    #
    # Also write an immutable audit record after successful delivery.
    pass
