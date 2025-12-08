"""Add audit logs table and database constraints

Revision ID: add_audit_constraints
Revises: 
Create Date: 2025-12-06
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "add_audit_constraints"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("user_email", sa.String(255), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=True),
        sa.Column("ip_address", sa.String(50), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("old_values", sa.Text(), nullable=True),
        sa.Column("new_values", sa.Text(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_resource_type", "audit_logs", ["resource_type"])
    
    # Add indexes to time_entries for performance
    op.create_index("ix_time_entries_user_date", "time_entries", ["user_id", "start_time"])
    op.create_index("ix_time_entries_project", "time_entries", ["project_id", "start_time"])
    
    # Add check constraint for positive duration
    op.execute("""
        ALTER TABLE time_entries 
        ADD CONSTRAINT ck_time_entries_positive_duration 
        CHECK (duration_seconds IS NULL OR duration_seconds >= 0)
    """)
    
    # Add check constraint for end_time > start_time
    op.execute("""
        ALTER TABLE time_entries 
        ADD CONSTRAINT ck_time_entries_valid_times 
        CHECK (end_time IS NULL OR end_time >= start_time)
    """)
    
    # Add soft delete column to users
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    
    # Add soft delete column to projects
    op.add_column("projects", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    
    # Add soft delete column to time_entries
    op.add_column("time_entries", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    
    # Add approval status to time_entries
    op.add_column("time_entries", sa.Column("approval_status", sa.String(20), server_default="pending", nullable=False))
    op.add_column("time_entries", sa.Column("approved_by", sa.Integer(), nullable=True))
    op.add_column("time_entries", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    # Remove approval columns
    op.drop_column("time_entries", "approved_at")
    op.drop_column("time_entries", "approved_by")
    op.drop_column("time_entries", "approval_status")
    
    # Remove soft delete columns
    op.drop_column("time_entries", "deleted_at")
    op.drop_column("projects", "deleted_at")
    op.drop_column("users", "deleted_at")
    
    # Remove constraints
    op.execute("ALTER TABLE time_entries DROP CONSTRAINT IF EXISTS ck_time_entries_valid_times")
    op.execute("ALTER TABLE time_entries DROP CONSTRAINT IF EXISTS ck_time_entries_positive_duration")
    
    # Remove indexes
    op.drop_index("ix_time_entries_project", "time_entries")
    op.drop_index("ix_time_entries_user_date", "time_entries")
    
    # Drop audit_logs table
    op.drop_index("ix_audit_logs_resource_type", "audit_logs")
    op.drop_index("ix_audit_logs_action", "audit_logs")
    op.drop_index("ix_audit_logs_user_id", "audit_logs")
    op.drop_index("ix_audit_logs_timestamp", "audit_logs")
    op.drop_table("audit_logs")
