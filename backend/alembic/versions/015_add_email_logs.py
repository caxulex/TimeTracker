"""Add email_logs table

Revision ID: 015_add_email_logs
Revises: 014_add_email_tracking_to_account_requests
Create Date: 2026-01-22

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '015_add_email_logs'
down_revision = '014_add_email_tracking_to_account_requests'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create email_logs table
    op.create_table(
        'email_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=True),
        sa.Column('to_email', sa.String(255), nullable=False),
        sa.Column('from_email', sa.String(255), nullable=False),
        sa.Column('subject', sa.String(500), nullable=False),
        sa.Column('email_type', sa.String(100), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('email_metadata', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('ix_email_logs_id', 'email_logs', ['id'])
    op.create_index('ix_email_logs_company_id', 'email_logs', ['company_id'])
    op.create_index('ix_email_logs_to_email', 'email_logs', ['to_email'])
    op.create_index('ix_email_logs_email_type', 'email_logs', ['email_type'])
    op.create_index('ix_email_logs_status', 'email_logs', ['status'])
    op.create_index('ix_email_log_company_date', 'email_logs', ['company_id', 'created_at'])
    op.create_index('ix_email_log_status_date', 'email_logs', ['status', 'created_at'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_email_log_status_date', table_name='email_logs')
    op.drop_index('ix_email_log_company_date', table_name='email_logs')
    op.drop_index('ix_email_logs_status', table_name='email_logs')
    op.drop_index('ix_email_logs_email_type', table_name='email_logs')
    op.drop_index('ix_email_logs_to_email', table_name='email_logs')
    op.drop_index('ix_email_logs_company_id', table_name='email_logs')
    op.drop_index('ix_email_logs_id', table_name='email_logs')
    
    # Drop table
    op.drop_table('email_logs')
