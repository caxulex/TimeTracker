"""Add AI Feature Toggle System tables

Revision ID: 009
Revises: 008
Create Date: 2025-12-31

Creates tables for:
- ai_feature_settings: Global AI feature configuration (admin controlled)
- user_ai_preferences: Per-user AI feature preferences
- ai_usage_log: AI usage tracking for cost monitoring
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade():
    # Table 1: Global AI feature settings (admin controlled)
    op.create_table(
        'ai_feature_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('feature_id', sa.String(50), nullable=False, unique=True),
        sa.Column('feature_name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('requires_api_key', sa.Boolean(), nullable=False, default=True),
        sa.Column('api_provider', sa.String(50), nullable=True),
        sa.Column('config', sa.JSON(), nullable=True, default={}),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id']),
    )
    
    # Indexes for ai_feature_settings
    op.create_index('ix_ai_feature_settings_id', 'ai_feature_settings', ['id'])
    op.create_index('ix_ai_feature_settings_feature_id', 'ai_feature_settings', ['feature_id'], unique=True)
    op.create_index('ix_ai_feature_settings_is_enabled', 'ai_feature_settings', ['is_enabled'])
    
    # Table 2: User-specific AI preferences
    op.create_table(
        'user_ai_preferences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('feature_id', sa.String(50), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('admin_override', sa.Boolean(), nullable=False, default=False),
        sa.Column('admin_override_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['admin_override_by'], ['users.id']),
        sa.UniqueConstraint('user_id', 'feature_id', name='uq_user_ai_preference'),
    )
    
    # Indexes for user_ai_preferences
    op.create_index('ix_user_ai_preferences_id', 'user_ai_preferences', ['id'])
    op.create_index('ix_user_ai_preferences_user_id', 'user_ai_preferences', ['user_id'])
    op.create_index('ix_user_ai_preferences_feature_id', 'user_ai_preferences', ['feature_id'])
    op.create_index('ix_user_ai_preferences_user_feature', 'user_ai_preferences', ['user_id', 'feature_id'])
    
    # Table 3: AI usage tracking for cost monitoring
    op.create_table(
        'ai_usage_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('feature_id', sa.String(50), nullable=False),
        sa.Column('api_provider', sa.String(50), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('estimated_cost', sa.Numeric(10, 6), nullable=True),
        sa.Column('request_timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False, default=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('request_metadata', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    )
    
    # Indexes for ai_usage_log
    op.create_index('ix_ai_usage_log_id', 'ai_usage_log', ['id'])
    op.create_index('ix_ai_usage_log_user_id', 'ai_usage_log', ['user_id'])
    op.create_index('ix_ai_usage_log_feature_id', 'ai_usage_log', ['feature_id'])
    op.create_index('ix_ai_usage_log_timestamp', 'ai_usage_log', ['request_timestamp'])
    op.create_index('ix_ai_usage_log_user_date', 'ai_usage_log', ['user_id', 'request_timestamp'])
    op.create_index('ix_ai_usage_log_feature_date', 'ai_usage_log', ['feature_id', 'request_timestamp'])
    
    # Insert default AI feature settings
    op.execute("""
        INSERT INTO ai_feature_settings (feature_id, feature_name, description, is_enabled, requires_api_key, api_provider)
        VALUES 
            ('ai_suggestions', 'Time Entry Suggestions', 'AI-powered suggestions for projects and tasks based on your work patterns', true, true, 'gemini'),
            ('ai_anomaly_alerts', 'Anomaly Detection', 'Automatic detection of unusual work patterns like overtime or missing entries', true, true, 'gemini'),
            ('ai_payroll_forecast', 'Payroll Forecasting', 'Predictive analytics for payroll and budget planning', false, true, 'gemini'),
            ('ai_nlp_entry', 'Natural Language Entry', 'Create time entries using natural language like "Log 2 hours on Project Alpha"', false, true, 'gemini'),
            ('ai_report_summaries', 'AI Report Summaries', 'AI-generated insights and summaries in your reports', false, true, 'gemini'),
            ('ai_task_estimation', 'Task Duration Estimation', 'AI-powered estimates for how long tasks will take', false, true, 'gemini')
    """)


def downgrade():
    # Drop ai_usage_log indexes and table
    op.drop_index('ix_ai_usage_log_feature_date', 'ai_usage_log')
    op.drop_index('ix_ai_usage_log_user_date', 'ai_usage_log')
    op.drop_index('ix_ai_usage_log_timestamp', 'ai_usage_log')
    op.drop_index('ix_ai_usage_log_feature_id', 'ai_usage_log')
    op.drop_index('ix_ai_usage_log_user_id', 'ai_usage_log')
    op.drop_index('ix_ai_usage_log_id', 'ai_usage_log')
    op.drop_table('ai_usage_log')
    
    # Drop user_ai_preferences indexes and table
    op.drop_index('ix_user_ai_preferences_user_feature', 'user_ai_preferences')
    op.drop_index('ix_user_ai_preferences_feature_id', 'user_ai_preferences')
    op.drop_index('ix_user_ai_preferences_user_id', 'user_ai_preferences')
    op.drop_index('ix_user_ai_preferences_id', 'user_ai_preferences')
    op.drop_table('user_ai_preferences')
    
    # Drop ai_feature_settings indexes and table
    op.drop_index('ix_ai_feature_settings_is_enabled', 'ai_feature_settings')
    op.drop_index('ix_ai_feature_settings_feature_id', 'ai_feature_settings')
    op.drop_index('ix_ai_feature_settings_id', 'ai_feature_settings')
    op.drop_table('ai_feature_settings')
