"""Add performance indexes for N+1 query optimization

Revision ID: 006_performance_indexes
Revises: 005_add_role
Create Date: 2025-12-22
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "006_performance_indexes"
down_revision = "005_add_role"
branch_labels = None
depends_on = None


def upgrade():
    """Add composite indexes for frequently queried relationships"""
    
    # Team memberships - frequently queried by user_id and team_id
    op.create_index(
        "ix_team_members_user_team", 
        "team_members", 
        ["user_id", "team_id"],
        unique=False
    )
    
    # Pay rates - frequently queried with user and active status
    op.create_index(
        "ix_pay_rates_user_active", 
        "pay_rates", 
        ["user_id", "is_active"],
        unique=False
    )
    
    # Pay rates - frequently queried by effective date for current rate
    op.create_index(
        "ix_pay_rates_effective_from", 
        "pay_rates", 
        ["effective_from", "is_active"],
        unique=False
    )
    
    # Time entries - improve user time queries by date range
    op.create_index(
        "ix_time_entries_user_start_time", 
        "time_entries", 
        ["user_id", "start_time"],
        unique=False
    )
    
    # Time entries - improve project-based queries
    op.create_index(
        "ix_time_entries_project_start_time", 
        "time_entries", 
        ["project_id", "start_time"],
        unique=False
    )
    
    # Payroll entries - improve user payroll queries
    op.create_index(
        "ix_payroll_entries_user_period", 
        "payroll_entries", 
        ["user_id", "period_id"],
        unique=False
    )
    
    # Users - improve manager hierarchy queries
    op.create_index(
        "ix_users_manager_id", 
        "users", 
        ["manager_id"],
        unique=False
    )
    
    # Users - improve employment queries
    op.create_index(
        "ix_users_employment_status", 
        "users", 
        ["employment_type", "is_active"],
        unique=False
    )
    
    # Users - improve department/job title searches
    op.create_index(
        "ix_users_department", 
        "users", 
        ["department"],
        unique=False
    )
    
    # Account requests - improve pending requests queries
    op.create_index(
        "ix_account_requests_status_created", 
        "account_requests", 
        ["status", "created_at"],
        unique=False
    )


def downgrade():
    """Remove performance indexes"""
    
    # Drop indexes in reverse order
    op.drop_index("ix_account_requests_status_created", table_name="account_requests")
    op.drop_index("ix_users_department", table_name="users")
    op.drop_index("ix_users_employment_status", table_name="users")
    op.drop_index("ix_users_manager_id", table_name="users")
    op.drop_index("ix_payroll_entries_user_period", table_name="payroll_entries")
    op.drop_index("ix_time_entries_project_start_time", table_name="time_entries")
    op.drop_index("ix_time_entries_user_start_time", table_name="time_entries")
    op.drop_index("ix_pay_rates_effective_from", table_name="pay_rates")
    op.drop_index("ix_pay_rates_user_active", table_name="pay_rates")
    op.drop_index("ix_team_members_user_team", table_name="team_members")
