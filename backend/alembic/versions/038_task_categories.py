"""Add categories and task_categories tables.

Revision ID: 038_task_categories
Revises: 037_api_keys_health_tracking
Create Date: 2026-06-08
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "038_task_categories"
down_revision = "037_api_keys_health_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
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

    seed_categories = [
        ("IT Security", "#DC2626"),
        ("SEO", "#10B981"),
        ("Dev", "#3B82F6"),
        ("Admin", "#F59E0B"),
        ("Reporting", "#8B5CF6"),
    ]

    for name, color in seed_categories:
        op.execute(
            sa.text(
                """
                INSERT INTO categories (company_id, name, color, created_at, updated_at)
                SELECT c.id, :name, :color, now(), now()
                FROM companies c
                ON CONFLICT (company_id, name) WHERE deleted_at IS NULL DO NOTHING
                """
            ).bindparams(name=name, color=color)
        )


def downgrade() -> None:
    op.drop_index("ix_task_categories_category_id_task_id", table_name="task_categories")
    op.drop_table("task_categories")

    op.drop_index("uq_categories_company_name_active", table_name="categories")
    op.drop_index("ix_categories_company_id_deleted_at", table_name="categories")
    op.drop_table("categories")
