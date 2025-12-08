"""Add comprehensive staff fields to users table

Revision ID: 003_staff_fields
Revises: 002_payroll_models
Create Date: 2025-12-08

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003_staff_fields'
down_revision = '002_payroll_models'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add employment and contact fields to users table
    op.add_column('users', sa.Column('phone', sa.String(50), nullable=True))
    op.add_column('users', sa.Column('job_title', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('department', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('employment_type', sa.String(50), nullable=True))  # full_time, part_time, contractor
    op.add_column('users', sa.Column('start_date', sa.Date, nullable=True))
    op.add_column('users', sa.Column('expected_hours_per_week', sa.Numeric(5, 2), nullable=True))
    op.add_column('users', sa.Column('manager_id', sa.Integer, sa.ForeignKey('users.id'), nullable=True))
    op.add_column('users', sa.Column('emergency_contact_name', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('emergency_contact_phone', sa.String(50), nullable=True))
    op.add_column('users', sa.Column('address', sa.Text, nullable=True))
    
    # Add indexes for new fields
    op.create_index('ix_users_department', 'users', ['department'])
    op.create_index('ix_users_employment_type', 'users', ['employment_type'])
    op.create_index('ix_users_manager_id', 'users', ['manager_id'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_users_manager_id', table_name='users')
    op.drop_index('ix_users_employment_type', table_name='users')
    op.drop_index('ix_users_department', table_name='users')
    
    # Drop columns
    op.drop_column('users', 'address')
    op.drop_column('users', 'emergency_contact_phone')
    op.drop_column('users', 'emergency_contact_name')
    op.drop_column('users', 'manager_id')
    op.drop_column('users', 'expected_hours_per_week')
    op.drop_column('users', 'start_date')
    op.drop_column('users', 'employment_type')
    op.drop_column('users', 'department')
    op.drop_column('users', 'job_title')
    op.drop_column('users', 'phone')
