"""Add teams soft-delete lifecycle columns.

Revision ID: 035_teams_soft_delete
Revises: 034_anomaly_dismissals
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "035_teams_soft_delete"
down_revision = "034_anomaly_dismissals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "teams",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "teams",
        sa.Column("deleted_by_user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "teams",
        sa.Column("delete_reason", sa.Text(), nullable=True),
    )

    op.create_foreign_key(
        "fk_teams_deleted_by_user_id",
        "teams",
        "users",
        ["deleted_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_index(
        "ix_teams_deleted_at",
        "teams",
        ["deleted_at"],
        unique=False,
    )
    op.execute(
        "CREATE INDEX idx_teams_company_active ON teams(company_id) WHERE deleted_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_teams_company_active")
    op.drop_index("ix_teams_deleted_at", table_name="teams")
    op.drop_constraint("fk_teams_deleted_by_user_id", "teams", type_="foreignkey")
    op.drop_column("teams", "delete_reason")
    op.drop_column("teams", "deleted_by_user_id")
    op.drop_column("teams", "deleted_at")
