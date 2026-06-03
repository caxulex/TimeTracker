"""Add project-team association table with backfill.

Revision ID: 036_project_teams_assoc
Revises: 035_teams_soft_delete
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "036_project_teams_assoc"
down_revision = "035_teams_soft_delete"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_teams",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("added_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["added_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("project_id", "team_id", name="uq_project_teams_project_team"),
    )
    op.create_index("ix_project_teams_project_id", "project_teams", ["project_id"], unique=False)
    op.create_index("ix_project_teams_team_id", "project_teams", ["team_id"], unique=False)

    # Backfill all existing projects so legacy visibility is preserved.
    op.execute(
        """
        INSERT INTO project_teams (project_id, team_id, added_at)
        SELECT id, team_id, NOW() FROM projects
        """
    )


def downgrade() -> None:
    op.drop_index("ix_project_teams_team_id", table_name="project_teams")
    op.drop_index("ix_project_teams_project_id", table_name="project_teams")
    op.drop_table("project_teams")
