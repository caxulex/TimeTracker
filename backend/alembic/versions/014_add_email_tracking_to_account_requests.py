"""Add email tracking fields to account_requests table

Revision ID: 014
Revises: 013
Create Date: 2026-01-21

This migration adds fields to track email notification status
for account approval/rejection notifications.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '014'
down_revision = '013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add email tracking fields to account_requests table
    op.add_column('account_requests', sa.Column('email_notification_sent', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('account_requests', sa.Column('email_sent_at', sa.DateTime(), nullable=True))
    op.add_column('account_requests', sa.Column('email_error', sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove email tracking fields from account_requests table
    op.drop_column('account_requests', 'email_error')
    op.drop_column('account_requests', 'email_sent_at')
    op.drop_column('account_requests', 'email_notification_sent')
