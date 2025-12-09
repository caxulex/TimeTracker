"""Add account_requests table

Revision ID: 004_account_requests
Revises: add_audit_constraints
Create Date: 2025-12-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '004_account_requests'
down_revision: Union[str, None] = 'add_audit_constraints'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create account_requests table
    op.create_table(
        'account_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('job_title', sa.String(length=255), nullable=True),
        sa.Column('department', sa.String(length=255), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('submitted_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('admin_notes', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected')", name='status_check'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', name='uq_account_requests_email')
    )
    
    # Create indexes for performance
    op.create_index('idx_account_requests_status', 'account_requests', ['status'])
    op.create_index('idx_account_requests_email', 'account_requests', ['email'])
    op.create_index('idx_account_requests_submitted', 'account_requests', ['submitted_at'], postgresql_using='btree', postgresql_ops={'submitted_at': 'DESC'})


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_account_requests_submitted', table_name='account_requests')
    op.drop_index('idx_account_requests_email', table_name='account_requests')
    op.drop_index('idx_account_requests_status', table_name='account_requests')
    
    # Drop table
    op.drop_table('account_requests')
