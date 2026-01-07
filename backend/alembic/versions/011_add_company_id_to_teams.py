"""Add company_id to teams for multi-tenancy isolation

Revision ID: 011
Revises: 010
Create Date: 2026-01-07 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add company_id column to teams table
    op.add_column('teams', sa.Column('company_id', sa.Integer(), nullable=True))
    op.create_index('ix_teams_company_id', 'teams', ['company_id'])
    op.create_foreign_key(
        'fk_teams_company_id',
        'teams', 'companies',
        ['company_id'], ['id']
    )
    
    # Update existing teams to have the same company_id as their owner
    # This ensures data consistency when migrating existing data
    op.execute("""
        UPDATE teams 
        SET company_id = users.company_id 
        FROM users 
        WHERE teams.owner_id = users.id 
        AND users.company_id IS NOT NULL
    """)


def downgrade() -> None:
    op.drop_constraint('fk_teams_company_id', 'teams', type_='foreignkey')
    op.drop_index('ix_teams_company_id', table_name='teams')
    op.drop_column('teams', 'company_id')
