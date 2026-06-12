"""Add working-days configuration columns.

Revision ID: 040_add_working_days
Revises: 039_task_teams
Create Date: 2026-06-12
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "040_add_working_days"
down_revision = "039_task_teams"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column(
            "working_days",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[0,1,2,3,4]'::json"),
        ),
    )
    op.add_column(
        "users",
        sa.Column("working_days", sa.JSON(), nullable=True),
    )

    # Explicit backfill for existing rows to keep semantics deterministic.
    op.execute(
        """
        UPDATE companies
        SET working_days = '[0,1,2,3,4]'::json
        WHERE working_days IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("users", "working_days")
    op.drop_column("companies", "working_days")
