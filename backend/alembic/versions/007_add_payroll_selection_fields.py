"""Add employee selection fields to payroll_periods

Revision ID: 007
Revises: 006_add_performance_indexes
Create Date: 2025-12-26

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006_add_performance_indexes'
branch_labels = None
depends_on = None


def upgrade():
    # Add selected_user_ids column to payroll_periods
    op.add_column(
        'payroll_periods',
        sa.Column('selected_user_ids', sa.Text(), nullable=True)
    )
    
    # Add rate_type_filter column to payroll_periods
    op.add_column(
        'payroll_periods',
        sa.Column('rate_type_filter', sa.String(20), nullable=True)
    )


def downgrade():
    op.drop_column('payroll_periods', 'rate_type_filter')
    op.drop_column('payroll_periods', 'selected_user_ids')
