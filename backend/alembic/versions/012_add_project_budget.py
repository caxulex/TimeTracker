"""Add project budget fields and history table

Revision ID: 012_add_project_budget
Revises: 011_add_company_id_to_teams
Create Date: 2026-01-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '012_add_project_budget'
down_revision = '011_add_company_id_to_teams'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add budget fields to projects table
    op.add_column('projects', sa.Column('budget_amount', sa.Numeric(precision=12, scale=2), nullable=True))
    op.add_column('projects', sa.Column('deadline', sa.Date(), nullable=True))
    
    # Create project_budget_history table for audit trail
    op.create_table(
        'project_budget_history',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('changed_by_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('old_budget_amount', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('new_budget_amount', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('old_deadline', sa.Date(), nullable=True),
        sa.Column('new_deadline', sa.Date(), nullable=True),
        sa.Column('change_reason', sa.String(500), nullable=True),
        sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    # Create index for efficient history queries
    op.create_index(
        'ix_project_budget_history_project_date',
        'project_budget_history',
        ['project_id', 'changed_at']
    )


def downgrade() -> None:
    # Drop the history table and index
    op.drop_index('ix_project_budget_history_project_date', table_name='project_budget_history')
    op.drop_table('project_budget_history')
    
    # Remove budget columns from projects
    op.drop_column('projects', 'deadline')
    op.drop_column('projects', 'budget_amount')
