"""Add meeting time entry tracking columns

Revision ID: 018_meeting_time_entries
Revises: 017_add_micro_task_management
Create Date: 2026-01-30

Adds paused_entry_id and time_entry_id to session_meetings table
to track the time entry created for meetings.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '018_meeting_time_entries'
down_revision = '017_add_micro_task_management'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add paused_entry_id - the time entry that was paused when meeting started
    op.add_column('session_meetings', 
        sa.Column('paused_entry_id', sa.Integer(), nullable=True)
    )
    
    # Add time_entry_id - the time entry created for the meeting itself
    op.add_column('session_meetings', 
        sa.Column('time_entry_id', sa.Integer(), nullable=True)
    )
    
    # Add foreign key constraints
    op.create_foreign_key(
        'fk_session_meetings_paused_entry',
        'session_meetings', 'time_entries',
        ['paused_entry_id'], ['id'],
        ondelete='SET NULL'
    )
    
    op.create_foreign_key(
        'fk_session_meetings_time_entry',
        'session_meetings', 'time_entries',
        ['time_entry_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    # Drop foreign key constraints first
    op.drop_constraint('fk_session_meetings_time_entry', 'session_meetings', type_='foreignkey')
    op.drop_constraint('fk_session_meetings_paused_entry', 'session_meetings', type_='foreignkey')
    
    # Drop columns
    op.drop_column('session_meetings', 'time_entry_id')
    op.drop_column('session_meetings', 'paused_entry_id')
