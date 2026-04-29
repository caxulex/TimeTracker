"""Add per-company overtime configuration columns (C2)

Adds three columns to the ``companies`` table so each tenant can opt in to
FLSA-compliant per-week overtime calculation. Existing companies receive the
defaults (overtime disabled) at migration time, so behavior is unchanged for
the currently deployed tenant.

Revision ID: 022_company_overtime_cfg
Revises: 021_unique_running_timer
Create Date: 2026-04-29
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "022_company_overtime_cfg"
down_revision = "021_unique_running_timer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column(
            "overtime_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "companies",
        sa.Column(
            "overtime_threshold_hours_per_week",
            sa.Numeric(5, 2),
            nullable=False,
            server_default=sa.text("40.00"),
        ),
    )
    op.add_column(
        "companies",
        sa.Column(
            "overtime_multiplier",
            sa.Numeric(3, 2),
            nullable=False,
            server_default=sa.text("1.50"),
        ),
    )


def downgrade() -> None:
    op.drop_column("companies", "overtime_multiplier")
    op.drop_column("companies", "overtime_threshold_hours_per_week")
    op.drop_column("companies", "overtime_enabled")
