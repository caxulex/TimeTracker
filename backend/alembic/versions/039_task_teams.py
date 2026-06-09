"""Replace task categories with task-team links.

Revision ID: 039_task_teams
Revises: 038_task_categories
Create Date: 2026-06-09
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "039_task_teams"
down_revision = "038_task_categories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "teams",
        sa.Column("color", sa.String(length=20), nullable=False, server_default="#6B7280"),
    )

    op.create_table(
        "task_teams",
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.PrimaryKeyConstraint("task_id", "team_id", name="pk_task_teams"),
    )
    op.create_index(
        "ix_task_teams_team_id_task_id",
        "task_teams",
        ["team_id", "task_id"],
        unique=False,
    )

    op.drop_index("ix_task_categories_category_id_task_id", table_name="task_categories")
    op.drop_table("task_categories")
    op.drop_index("uq_categories_company_name_active", table_name="categories")
    op.drop_index("ix_categories_company_id_deleted_at", table_name="categories")
    op.drop_table("categories")


def downgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=False, server_default="#6B7280"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index(
        "ix_categories_company_id_deleted_at",
        "categories",
        ["company_id", "deleted_at"],
        unique=False,
    )
    op.create_index(
        "uq_categories_company_name_active",
        "categories",
        ["company_id", "name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "task_categories",
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.PrimaryKeyConstraint("task_id", "category_id", name="pk_task_categories"),
    )
    op.create_index(
        "ix_task_categories_category_id_task_id",
        "task_categories",
        ["category_id", "task_id"],
        unique=False,
    )

    op.drop_index("ix_task_teams_team_id_task_id", table_name="task_teams")
    op.drop_table("task_teams")
    op.drop_column("teams", "color")
