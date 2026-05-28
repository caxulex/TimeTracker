"""Add Basecamp webhook subscriptions and processed-event dedupe.

Revision ID: 032_bc_webhook_subs
Revises: 031_basecamp_orphan_cleanup
Create Date: 2026-05-28
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "032_bc_webhook_subs"
down_revision = "031_basecamp_orphan_cleanup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "basecamp_credentials",
        sa.Column("webhook_secret_hash", sa.String(length=128), nullable=True),
    )

    op.create_table(
        "basecamp_webhook_subscriptions",
        sa.Column("id", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column("credentials_id", sa.BigInteger(), nullable=False),
        sa.Column("basecamp_project_id", sa.String(length=64), nullable=False),
        sa.Column("basecamp_webhook_id", sa.String(length=64), nullable=False),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["credentials_id"],
            ["basecamp_credentials.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "credentials_id",
            "basecamp_project_id",
            name="uq_basecamp_webhook_subscription_project",
        ),
    )
    op.create_index(
        "ix_basecamp_webhook_subscriptions_credentials_id",
        "basecamp_webhook_subscriptions",
        ["credentials_id"],
    )
    op.create_index(
        "ix_basecamp_webhook_subscriptions_active",
        "basecamp_webhook_subscriptions",
        ["active"],
    )

    op.create_table(
        "basecamp_processed_events",
        sa.Column("event_id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_basecamp_processed_events_processed_at",
        "basecamp_processed_events",
        ["processed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_basecamp_processed_events_processed_at",
        table_name="basecamp_processed_events",
    )
    op.drop_table("basecamp_processed_events")

    op.drop_index(
        "ix_basecamp_webhook_subscriptions_active",
        table_name="basecamp_webhook_subscriptions",
    )
    op.drop_index(
        "ix_basecamp_webhook_subscriptions_credentials_id",
        table_name="basecamp_webhook_subscriptions",
    )
    op.drop_table("basecamp_webhook_subscriptions")

    op.drop_column("basecamp_credentials", "webhook_secret_hash")
