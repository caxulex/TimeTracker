"""Add disambiguation metadata to basecamp_task_mappings

Revision ID: 027_bc_task_mapping_metadata
Revises: 026_basecamp_task_mappings
Create Date: 2026-05-12

Adds three nullable columns to ``basecamp_task_mappings`` so the
TimeTracker dashboard can disambiguate Basecamp-mirrored to-dos that
share the same name (e.g. "Generate Monthly Report" appearing once
per month under a single to-do list):

* ``basecamp_due_on`` (Date)
* ``basecamp_todo_created_at`` (DateTime with timezone)
* ``basecamp_todo_position`` (Integer)

All columns are nullable so the existing 6020 mapping rows in
production remain valid after the migration. Values backfill on the
next sync run; no data migration is performed here.

Round-trips cleanly (upgrade -> downgrade -> upgrade).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Kept under 32 chars to fit ``alembic_version.version_num``
# VARCHAR(32) without overflowing.
revision = "027_bc_task_mapping_metadata"
down_revision = "026_basecamp_task_mappings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "basecamp_task_mappings",
        sa.Column("basecamp_due_on", sa.Date(), nullable=True),
    )
    op.add_column(
        "basecamp_task_mappings",
        sa.Column(
            "basecamp_todo_created_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "basecamp_task_mappings",
        sa.Column("basecamp_todo_position", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("basecamp_task_mappings", "basecamp_todo_position")
    op.drop_column("basecamp_task_mappings", "basecamp_todo_created_at")
    op.drop_column("basecamp_task_mappings", "basecamp_due_on")
