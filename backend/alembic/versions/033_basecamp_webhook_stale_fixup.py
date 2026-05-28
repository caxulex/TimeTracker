"""Clear false-positive stale webhook errors for newly created subscriptions.

Revision ID: 033_bc_webhook_stale_fix
Revises: 032_bc_webhook_subs
Create Date: 2026-05-28
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "033_bc_webhook_stale_fix"
down_revision = "032_bc_webhook_subs"
branch_labels = None
depends_on = None


CLEAR_FALSE_POSITIVE_STALE_ERRORS_SQL = """
UPDATE basecamp_webhook_subscriptions
SET last_error = NULL,
    last_error_at = NULL
WHERE last_error LIKE 'No webhook events%'
  AND last_event_at IS NULL
  AND created_at > NOW() - INTERVAL '7 days'
"""


def upgrade() -> None:
    op.execute(sa.text(CLEAR_FALSE_POSITIVE_STALE_ERRORS_SQL))


def downgrade() -> None:
    # Data cleanup migration is intentionally irreversible.
    pass
