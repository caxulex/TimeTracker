"""Make project_id nullable on time_entries

Revision ID: 019_nullable_project
Revises: 018_meeting_time_entries
Create Date: 2026-02-06

Meetings create time entries without a project, so project_id
must be nullable. This is a safe change - existing entries with
a project_id are unaffected.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '019_nullable_project'
down_revision = '018_meeting_time_entries'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make project_id nullable so meetings can have time entries without projects
    op.alter_column(
        'time_entries',
        'project_id',
        existing_type=sa.Integer(),
        nullable=True
    )


def downgrade() -> None:
    # Revert: set project_id back to NOT NULL
    # (must first delete any rows with NULL project_id)
    op.execute("DELETE FROM time_entries WHERE project_id IS NULL")
    op.alter_column(
        'time_entries',
        'project_id',
        existing_type=sa.Integer(),
        nullable=False
    )
