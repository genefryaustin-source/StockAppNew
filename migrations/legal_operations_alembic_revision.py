"""Add legal operations and override tables.

Replace revision and down_revision before use.
"""

from alembic import op
import sqlalchemy as sa


revision = "REPLACE_WITH_REVISION_ID"
down_revision = "REPLACE_WITH_CURRENT_HEAD"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "legal_access_overrides",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=160), nullable=False),
        sa.Column("tenant_id", sa.String(length=160), nullable=True),
        sa.Column("acknowledgement_id", sa.String(length=36), nullable=True),
        sa.Column("document_key", sa.String(length=160), nullable=True),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.String(length=64), nullable=True),
        sa.Column("revoked_at", sa.String(length=64), nullable=True),
        sa.Column("revoked_by", sa.String(length=160), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False),
    )
    op.create_index(
        "ix_legal_access_overrides_user",
        "legal_access_overrides",
        ["user_id"],
    )
    op.create_index(
        "ix_legal_access_overrides_tenant",
        "legal_access_overrides",
        ["tenant_id"],
    )

    op.create_table(
        "legal_notification_deliveries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("notification_key", sa.String(length=128), nullable=False),
        sa.Column("notification_type", sa.String(length=100), nullable=False),
        sa.Column("recipient_user_id", sa.String(length=160), nullable=False),
        sa.Column("recipient_email", sa.String(length=320), nullable=True),
        sa.Column("acknowledgement_id", sa.String(length=36), nullable=True),
        sa.Column("document_key", sa.String(length=160), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.UniqueConstraint(
            "notification_key",
            name="uq_legal_notification_delivery_key",
        ),
    )


def downgrade() -> None:
    op.drop_table("legal_notification_deliveries")
    op.drop_table("legal_access_overrides")
