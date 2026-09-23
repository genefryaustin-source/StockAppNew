"""Add legal workflow persistence tables.

Copy this file into the project's Alembic versions directory and replace:
- revision
- down_revision
"""

from alembic import op
import sqlalchemy as sa


revision = "REPLACE_WITH_REVISION_ID"
down_revision = "REPLACE_WITH_CURRENT_HEAD"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "legal_document_versions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_key", sa.String(length=160), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("effective_date", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=160), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.String(length=160), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.UniqueConstraint(
            "document_key",
            "version",
            name="uq_legal_document_versions_key_version",
        ),
    )
    op.create_index(
        "ix_legal_document_versions_status",
        "legal_document_versions",
        ["status"],
    )
    op.create_index(
        "ix_legal_document_versions_document_key",
        "legal_document_versions",
        ["document_key"],
    )

    op.create_table(
        "legal_document_reviews",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "document_version_id",
            sa.String(length=36),
            sa.ForeignKey(
                "legal_document_versions.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "reviewer_user_id",
            sa.String(length=160),
            nullable=False,
        ),
        sa.Column("decision", sa.String(length=40), nullable=False),
        sa.Column("comments", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_legal_document_reviews_version",
        "legal_document_reviews",
        ["document_version_id"],
    )

    op.create_table(
        "legal_acknowledgements",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_key", sa.String(length=160), nullable=False),
        sa.Column("document_version", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=160), nullable=False),
        sa.Column("tenant_id", sa.String(length=160), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.String(length=64), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.String(length=128), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.UniqueConstraint(
            "document_key",
            "document_version",
            "user_id",
            name="uq_legal_ack_document_version_user",
        ),
    )
    op.create_index(
        "ix_legal_ack_user_status",
        "legal_acknowledgements",
        ["user_id", "status"],
    )
    op.create_index(
        "ix_legal_ack_tenant_status",
        "legal_acknowledgements",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_legal_ack_document_key",
        "legal_acknowledgements",
        ["document_key"],
    )

    op.create_table(
        "legal_workflow_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("document_key", sa.String(length=160), nullable=True),
        sa.Column(
            "document_version_id",
            sa.String(length=36),
            nullable=True,
        ),
        sa.Column(
            "acknowledgement_id",
            sa.String(length=36),
            nullable=True,
        ),
        sa.Column(
            "actor_user_id",
            sa.String(length=160),
            nullable=True,
        ),
        sa.Column("tenant_id", sa.String(length=160), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
    )
    op.create_index(
        "ix_legal_workflow_events_type",
        "legal_workflow_events",
        ["event_type"],
    )
    op.create_index(
        "ix_legal_workflow_events_document",
        "legal_workflow_events",
        ["document_key"],
    )
    op.create_index(
        "ix_legal_workflow_events_tenant",
        "legal_workflow_events",
        ["tenant_id"],
    )
    op.create_index(
        "ix_legal_workflow_events_occurred",
        "legal_workflow_events",
        ["occurred_at"],
    )


def downgrade() -> None:
    op.drop_table("legal_workflow_events")
    op.drop_table("legal_acknowledgements")
    op.drop_table("legal_document_reviews")
    op.drop_table("legal_document_versions")
