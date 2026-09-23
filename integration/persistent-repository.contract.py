# Implement this protocol against the existing StockApp database before
# enabling production acknowledgement enforcement.

from modules.legal_portal.legal_workflow_repository import LegalWorkflowRepository


class SqlLegalWorkflowRepository:
    # Required methods:
    #
    # create_version(...)
    # list_versions(...)
    # get_version(...)
    # update_status(...)
    # add_review(...)
    # list_reviews(...)
    # request_acknowledgement(...)
    # respond_to_acknowledgement(...)
    # list_acknowledgements(...)
    # summary(...)
    #
    # Store immutable review and acknowledgement events.
    # Use database transactions and unique constraints for:
    #
    # (document_key, version)
    # (document_key, document_version, user_id)
    #
    pass
