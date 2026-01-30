"""add micro task management tables

Revision ID: 017_add_micro_task
Revises: 016_add_notifications
Create Date: 2026-01-30

This migration adds:
- work_sessions table: Tracks user work days/sessions
- session_breaks table: Tracks break periods within sessions
- session_meetings table: Tracks meeting periods within sessions
- New columns on time_entries: work_session_id, is_paused, paused_at, pause_seconds

SAFETY NOTES:
- All new FK columns are NULLABLE for backward compatibility
- No existing columns are removed or renamed
- No data migration required - existing time_entries will have NULL work_session_id
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '017_add_micro_task'
down_revision = '016_add_notifications'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create work_sessions table
    op.create_table(
        'work_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=True),
        sa.Column('start_time', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_work_seconds', sa.Integer(), nullable=False, default=0),
        sa.Column('total_break_seconds', sa.Integer(), nullable=False, default=0),
        sa.Column('total_meeting_seconds', sa.Integer(), nullable=False, default=0),
        sa.Column('status', sa.String(20), nullable=False, default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_work_sessions_id', 'work_sessions', ['id'], unique=False)
    op.create_index('ix_work_sessions_user_id', 'work_sessions', ['user_id'], unique=False)
    op.create_index('ix_work_sessions_company_id', 'work_sessions', ['company_id'], unique=False)
    op.create_index('ix_work_sessions_status', 'work_sessions', ['status'], unique=False)

    # Create session_breaks table
    op.create_table(
        'session_breaks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('work_session_id', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=False, default=0),
        sa.Column('break_type', sa.String(20), nullable=False, default='short'),
        sa.ForeignKeyConstraint(['work_session_id'], ['work_sessions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_session_breaks_id', 'session_breaks', ['id'], unique=False)
    op.create_index('ix_session_breaks_work_session_id', 'session_breaks', ['work_session_id'], unique=False)

    # Create session_meetings table
    op.create_table(
        'session_meetings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('work_session_id', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=False, default=0),
        sa.Column('title', sa.String(200), nullable=True),
        sa.Column('meeting_type', sa.String(20), nullable=False, default='internal'),
        sa.ForeignKeyConstraint(['work_session_id'], ['work_sessions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_session_meetings_id', 'session_meetings', ['id'], unique=False)
    op.create_index('ix_session_meetings_work_session_id', 'session_meetings', ['work_session_id'], unique=False)

    # Add new columns to time_entries table (ALL NULLABLE for backward compatibility!)
    op.add_column('time_entries', sa.Column('work_session_id', sa.Integer(), nullable=True))
    op.add_column('time_entries', sa.Column('is_paused', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('time_entries', sa.Column('paused_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('time_entries', sa.Column('pause_seconds', sa.Integer(), nullable=False, server_default='0'))
    
    # Add foreign key constraint for work_session_id
    op.create_foreign_key(
        'fk_time_entries_work_session_id',
        'time_entries',
        'work_sessions',
        ['work_session_id'],
        ['id']
    )
    
    # Add index for work_session_id lookups
    op.create_index('ix_time_entries_work_session_id', 'time_entries', ['work_session_id'], unique=False)


def downgrade() -> None:
    # Remove index and foreign key from time_entries
    op.drop_index('ix_time_entries_work_session_id', table_name='time_entries')
    op.drop_constraint('fk_time_entries_work_session_id', 'time_entries', type_='foreignkey')
    
    # Remove columns from time_entries
    op.drop_column('time_entries', 'pause_seconds')
    op.drop_column('time_entries', 'paused_at')
    op.drop_column('time_entries', 'is_paused')
    op.drop_column('time_entries', 'work_session_id')
    
    # Drop session_meetings table
    op.drop_index('ix_session_meetings_work_session_id', table_name='session_meetings')
    op.drop_index('ix_session_meetings_id', table_name='session_meetings')
    op.drop_table('session_meetings')
    
    # Drop session_breaks table
    op.drop_index('ix_session_breaks_work_session_id', table_name='session_breaks')
    op.drop_index('ix_session_breaks_id', table_name='session_breaks')
    op.drop_table('session_breaks')
    
    # Drop work_sessions table
    op.drop_index('ix_work_sessions_status', table_name='work_sessions')
    op.drop_index('ix_work_sessions_company_id', table_name='work_sessions')
    op.drop_index('ix_work_sessions_user_id', table_name='work_sessions')
    op.drop_index('ix_work_sessions_id', table_name='work_sessions')
    op.drop_table('work_sessions')
