"""Add payroll models

Revision ID: 002_payroll_models
Revises: 001_initial
Create Date: 2025-01-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_payroll_models'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create pay_rates table
    op.create_table(
        'pay_rates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('rate_type', sa.String(20), nullable=False, server_default='hourly'),
        sa.Column('base_rate', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='USD'),
        sa.Column('overtime_multiplier', sa.Numeric(4, 2), nullable=False, server_default='1.5'),
        sa.Column('effective_from', sa.Date(), nullable=False),
        sa.Column('effective_to', sa.Date(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_pay_rates_id', 'pay_rates', ['id'], unique=False)
    op.create_index('ix_pay_rates_user_id', 'pay_rates', ['user_id'], unique=False)
    op.create_index('ix_pay_rates_effective_from', 'pay_rates', ['effective_from'], unique=False)
    op.create_index('ix_pay_rates_user_effective', 'pay_rates', ['user_id', 'effective_from'], unique=False)

    # Create pay_rate_history table
    op.create_table(
        'pay_rate_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pay_rate_id', sa.Integer(), nullable=False),
        sa.Column('previous_rate', sa.Numeric(10, 2), nullable=False),
        sa.Column('new_rate', sa.Numeric(10, 2), nullable=False),
        sa.Column('previous_overtime_multiplier', sa.Numeric(4, 2), nullable=True),
        sa.Column('new_overtime_multiplier', sa.Numeric(4, 2), nullable=True),
        sa.Column('changed_by', sa.Integer(), nullable=False),
        sa.Column('change_reason', sa.Text(), nullable=True),
        sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['pay_rate_id'], ['pay_rates.id'], ),
        sa.ForeignKeyConstraint(['changed_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_pay_rate_history_id', 'pay_rate_history', ['id'], unique=False)
    op.create_index('ix_pay_rate_history_pay_rate_id', 'pay_rate_history', ['pay_rate_id'], unique=False)

    # Create payroll_periods table
    op.create_table(
        'payroll_periods',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('period_type', sa.String(20), nullable=False, server_default='monthly'),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('total_amount', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('approved_by', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_payroll_periods_id', 'payroll_periods', ['id'], unique=False)
    op.create_index('ix_payroll_periods_start_date', 'payroll_periods', ['start_date'], unique=False)
    op.create_index('ix_payroll_periods_end_date', 'payroll_periods', ['end_date'], unique=False)
    op.create_index('ix_payroll_periods_status', 'payroll_periods', ['status'], unique=False)
    op.create_index('ix_payroll_periods_dates', 'payroll_periods', ['start_date', 'end_date'], unique=False)

    # Create payroll_entries table
    op.create_table(
        'payroll_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('payroll_period_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('regular_hours', sa.Numeric(8, 2), nullable=False, server_default='0.00'),
        sa.Column('overtime_hours', sa.Numeric(8, 2), nullable=False, server_default='0.00'),
        sa.Column('regular_rate', sa.Numeric(10, 2), nullable=False, server_default='0.00'),
        sa.Column('overtime_rate', sa.Numeric(10, 2), nullable=False, server_default='0.00'),
        sa.Column('gross_amount', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('adjustments_amount', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('net_amount', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['payroll_period_id'], ['payroll_periods.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_payroll_entries_id', 'payroll_entries', ['id'], unique=False)
    op.create_index('ix_payroll_entries_payroll_period_id', 'payroll_entries', ['payroll_period_id'], unique=False)
    op.create_index('ix_payroll_entries_user_id', 'payroll_entries', ['user_id'], unique=False)
    op.create_index('ix_payroll_entries_period_user', 'payroll_entries', ['payroll_period_id', 'user_id'], unique=False)

    # Create payroll_adjustments table
    op.create_table(
        'payroll_adjustments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('payroll_entry_id', sa.Integer(), nullable=False),
        sa.Column('adjustment_type', sa.String(20), nullable=False),
        sa.Column('description', sa.String(500), nullable=False),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['payroll_entry_id'], ['payroll_entries.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_payroll_adjustments_id', 'payroll_adjustments', ['id'], unique=False)
    op.create_index('ix_payroll_adjustments_payroll_entry_id', 'payroll_adjustments', ['payroll_entry_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_payroll_adjustments_payroll_entry_id', table_name='payroll_adjustments')
    op.drop_index('ix_payroll_adjustments_id', table_name='payroll_adjustments')
    op.drop_table('payroll_adjustments')
    
    op.drop_index('ix_payroll_entries_period_user', table_name='payroll_entries')
    op.drop_index('ix_payroll_entries_user_id', table_name='payroll_entries')
    op.drop_index('ix_payroll_entries_payroll_period_id', table_name='payroll_entries')
    op.drop_index('ix_payroll_entries_id', table_name='payroll_entries')
    op.drop_table('payroll_entries')
    
    op.drop_index('ix_payroll_periods_dates', table_name='payroll_periods')
    op.drop_index('ix_payroll_periods_status', table_name='payroll_periods')
    op.drop_index('ix_payroll_periods_end_date', table_name='payroll_periods')
    op.drop_index('ix_payroll_periods_start_date', table_name='payroll_periods')
    op.drop_index('ix_payroll_periods_id', table_name='payroll_periods')
    op.drop_table('payroll_periods')
    
    op.drop_index('ix_pay_rate_history_pay_rate_id', table_name='pay_rate_history')
    op.drop_index('ix_pay_rate_history_id', table_name='pay_rate_history')
    op.drop_table('pay_rate_history')
    
    op.drop_index('ix_pay_rates_user_effective', table_name='pay_rates')
    op.drop_index('ix_pay_rates_effective_from', table_name='pay_rates')
    op.drop_index('ix_pay_rates_user_id', table_name='pay_rates')
    op.drop_index('ix_pay_rates_id', table_name='pay_rates')
    op.drop_table('pay_rates')
