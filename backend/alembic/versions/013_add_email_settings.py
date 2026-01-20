"""Add email/SMTP settings to companies table

Revision ID: 013
Revises: 012
Create Date: 2026-01-20

This migration adds SMTP configuration fields to the companies table
to support per-company email settings for white-label support.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add SMTP/email configuration fields to companies table
    op.add_column('companies', sa.Column('smtp_server', sa.String(255), nullable=True))
    op.add_column('companies', sa.Column('smtp_port', sa.Integer(), nullable=False, server_default='587'))
    op.add_column('companies', sa.Column('smtp_username', sa.String(255), nullable=True))
    op.add_column('companies', sa.Column('smtp_password_encrypted', sa.Text(), nullable=True))
    op.add_column('companies', sa.Column('smtp_from_email', sa.String(255), nullable=True))
    op.add_column('companies', sa.Column('smtp_from_name', sa.String(255), nullable=True))
    op.add_column('companies', sa.Column('smtp_use_tls', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('companies', sa.Column('email_enabled', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    # Remove SMTP/email configuration fields from companies table
    op.drop_column('companies', 'email_enabled')
    op.drop_column('companies', 'smtp_use_tls')
    op.drop_column('companies', 'smtp_from_name')
    op.drop_column('companies', 'smtp_from_email')
    op.drop_column('companies', 'smtp_password_encrypted')
    op.drop_column('companies', 'smtp_username')
    op.drop_column('companies', 'smtp_port')
    op.drop_column('companies', 'smtp_server')
