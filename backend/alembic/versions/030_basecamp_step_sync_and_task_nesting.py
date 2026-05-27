"""Add task nesting and Basecamp step sync metadata

Revision ID: 030_bc_step_sync_nesting
Revises: 029_backfill_time_entry_desc
Create Date: 2026-05-27
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "030_bc_step_sync_nesting"
down_revision = "029_backfill_time_entry_desc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("parent_task_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_tasks_parent_task_id_tasks",
        "tasks",
        "tasks",
        ["parent_task_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_tasks_parent_task_id", "tasks", ["parent_task_id"])

    op.add_column(
        "basecamp_task_mappings",
        sa.Column(
            "basecamp_type",
            sa.String(length=32),
            nullable=False,
            server_default="Todo",
        ),
    )
    op.add_column(
        "basecamp_task_mappings",
        sa.Column("basecamp_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_basecamp_task_mappings_basecamp_type",
        "basecamp_task_mappings",
        ["basecamp_type"],
    )

    op.drop_constraint(
        "uq_basecamp_task_mapping_external",
        "basecamp_task_mappings",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_basecamp_task_mapping_external",
        "basecamp_task_mappings",
        [
            "company_id",
            "basecamp_account_id",
            "basecamp_type",
            "basecamp_todo_id",
        ],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_basecamp_task_mapping_external",
        "basecamp_task_mappings",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_basecamp_task_mapping_external",
        "basecamp_task_mappings",
        ["company_id", "basecamp_account_id", "basecamp_todo_id"],
    )

    op.drop_index(
        "ix_basecamp_task_mappings_basecamp_type",
        table_name="basecamp_task_mappings",
    )
    op.drop_column("basecamp_task_mappings", "basecamp_updated_at")
    op.drop_column("basecamp_task_mappings", "basecamp_type")

    op.drop_index("ix_tasks_parent_task_id", table_name="tasks")
    op.drop_constraint("fk_tasks_parent_task_id_tasks", "tasks", type_="foreignkey")
    op.drop_column("tasks", "parent_task_id")
