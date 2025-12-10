"""add role to team_members

Revision ID: 005_add_role
Revises: 004_account_requests
Create Date: 2025-12-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005_add_role'
down_revision: Union[str, None] = '004_account_requests'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add role column to team_members
    op.add_column('team_members', sa.Column('role', sa.String(length=50), nullable=False, server_default='member'))


def downgrade() -> None:
    # Remove role column from team_members
    op.drop_column('team_members', 'role')
