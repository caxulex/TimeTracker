"""Make Stripe webhook processed_at nullable for checkout scoped process-state.

Revision ID: 044_swh_processed_at_null
Revises: 043_stripe_webhook_events
Create Date: 2026-07-13
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "044_swh_processed_at_null"
down_revision = "043_stripe_webhook_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "stripe_webhook_events",
        "processed_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        server_default=None,
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE stripe_webhook_events
        SET processed_at = now()
        WHERE processed_at IS NULL
        """
    )
    op.alter_column(
        "stripe_webhook_events",
        "processed_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
