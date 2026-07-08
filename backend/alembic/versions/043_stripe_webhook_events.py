"""Add Stripe webhook events idempotency table.

Revision ID: 043_stripe_webhook_events
Revises: 042_tier_values
Create Date: 2026-07-08
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "043_stripe_webhook_events"
down_revision = "042_tier_values"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stripe_webhook_events",
        sa.Column("event_id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_stripe_webhook_events_processed_at",
        "stripe_webhook_events",
        ["processed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_stripe_webhook_events_processed_at",
        table_name="stripe_webhook_events",
    )
    op.drop_table("stripe_webhook_events")