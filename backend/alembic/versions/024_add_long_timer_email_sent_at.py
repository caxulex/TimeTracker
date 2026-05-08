"""Add long_timer_email_sent_at to time_entries

Revision ID: 024_long_timer_email
Revises: 023_basecamp_integration
Create Date: 2026-05-08

Adds a single nullable timestamp column to ``time_entries`` used by the
hourly long-timer warning job (``backend/scripts/send_long_timer_warnings.py``)
to make the warning email idempotent: an entry whose timer has been running
for more than 9 hours triggers a single email, and that email's send time
is stamped here so subsequent hourly runs skip the entry.

NULL = no warning email has been sent for this entry yet. Existing rows
intentionally default to NULL: timers that started before this feature
shipped will not retroactively trigger emails.

Round-trips cleanly (upgrade -> downgrade -> upgrade).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "024_long_timer_email"
down_revision = "023_basecamp_integration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "time_entries",
        sa.Column(
            "long_timer_email_sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("time_entries", "long_timer_email_sent_at")
