"""Add company and white label tables for multi-tenancy

Revision ID: 010
Revises: 009
Create Date: 2026-01-07 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone, timedelta


# revision identifiers, used by Alembic.
revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create companies table
    op.create_table(
        'companies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(100), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('subscription_tier', sa.String(50), nullable=False, server_default='trial'),
        sa.Column('status', sa.String(50), nullable=False, server_default='trial'),
        sa.Column('trial_ends_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('subscription_ends_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('max_users', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('max_projects', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('timezone', sa.String(50), nullable=False, server_default='UTC'),
        sa.Column('date_format', sa.String(20), nullable=False, server_default='YYYY-MM-DD'),
        sa.Column('time_format', sa.String(20), nullable=False, server_default='HH:mm'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_companies_id', 'companies', ['id'])
    op.create_index('ix_companies_slug', 'companies', ['slug'], unique=True)
    
    # Create white_label_configs table
    op.create_table(
        'white_label_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('custom_domain', sa.String(255), nullable=True),
        sa.Column('subdomain', sa.String(100), nullable=True),
        sa.Column('app_name', sa.String(100), nullable=False, server_default='Time Tracker'),
        sa.Column('company_name', sa.String(255), nullable=False),
        sa.Column('tagline', sa.String(255), nullable=True),
        sa.Column('logo_url', sa.String(500), nullable=True),
        sa.Column('favicon_url', sa.String(500), nullable=True),
        sa.Column('login_background_url', sa.String(500), nullable=True),
        sa.Column('primary_color', sa.String(7), nullable=False, server_default='#2563eb'),
        sa.Column('secondary_color', sa.String(7), nullable=True),
        sa.Column('accent_color', sa.String(7), nullable=True),
        sa.Column('support_email', sa.String(255), nullable=True),
        sa.Column('support_url', sa.String(500), nullable=True),
        sa.Column('terms_url', sa.String(500), nullable=True),
        sa.Column('privacy_url', sa.String(500), nullable=True),
        sa.Column('show_powered_by', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('custom_css', sa.Text(), nullable=True),
        sa.Column('custom_js', sa.Text(), nullable=True),
        sa.Column('email_from_name', sa.String(255), nullable=True),
        sa.Column('email_from_address', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_white_label_configs_id', 'white_label_configs', ['id'])
    op.create_index('ix_white_label_configs_company_id', 'white_label_configs', ['company_id'], unique=True)
    op.create_index('ix_white_label_configs_custom_domain', 'white_label_configs', ['custom_domain'], unique=True)
    op.create_index('ix_white_label_configs_subdomain', 'white_label_configs', ['subdomain'], unique=True)
    
    # Add company_id to users table (nullable for platform super_admins)
    op.add_column('users', sa.Column('company_id', sa.Integer(), nullable=True))
    op.create_index('ix_users_company_id', 'users', ['company_id'])
    op.create_foreign_key(
        'fk_users_company_id',
        'users',
        'companies',
        ['company_id'],
        ['id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    # Remove foreign key and column from users
    op.drop_constraint('fk_users_company_id', 'users', type_='foreignkey')
    op.drop_index('ix_users_company_id', 'users')
    op.drop_column('users', 'company_id')
    
    # Drop white_label_configs table
    op.drop_index('ix_white_label_configs_subdomain', 'white_label_configs')
    op.drop_index('ix_white_label_configs_custom_domain', 'white_label_configs')
    op.drop_index('ix_white_label_configs_company_id', 'white_label_configs')
    op.drop_index('ix_white_label_configs_id', 'white_label_configs')
    op.drop_table('white_label_configs')
    
    # Drop companies table
    op.drop_index('ix_companies_slug', 'companies')
    op.drop_index('ix_companies_id', 'companies')
    op.drop_table('companies')
