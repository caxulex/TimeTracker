"""Add api_keys table for AI provider credentials

Revision ID: 008
Revises: 007
Create Date: 2025-12-31

SEC-020: Secure API Key Storage for AI Integrations
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade():
    # Create api_keys table
    op.create_table(
        'api_keys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('encrypted_key', sa.Text(), nullable=False),
        sa.Column('key_preview', sa.String(20), nullable=False),
        sa.Column('label', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=False, default=0),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    )
    
    # Create indexes
    op.create_index('ix_api_keys_id', 'api_keys', ['id'])
    op.create_index('ix_api_keys_provider', 'api_keys', ['provider'])
    op.create_index('ix_api_keys_is_active', 'api_keys', ['is_active'])
    op.create_index('ix_api_keys_provider_active', 'api_keys', ['provider', 'is_active'])


def downgrade():
    # Drop indexes
    op.drop_index('ix_api_keys_provider_active', 'api_keys')
    op.drop_index('ix_api_keys_is_active', 'api_keys')
    op.drop_index('ix_api_keys_provider', 'api_keys')
    op.drop_index('ix_api_keys_id', 'api_keys')
    
    # Drop table
    op.drop_table('api_keys')
