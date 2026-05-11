"""Add basecamp_task_mappings table

Revision ID: 026_basecamp_task_mappings
Revises: 025_basecamp_target_team
Create Date: 2026-05-11

Adds the mapping table that backs Basecamp -> TimeTracker one-way
to-do mirroring (v3.0). Each row links a single Basecamp to-do (under
a specific account + project + to-do list) to an internal
``tasks.id`` row, so the to-do sync is idempotent.

The triple ``(company_id, basecamp_account_id, basecamp_todo_id)`` is
UNIQUE. ``company_id`` is included in the constraint so the same
Basecamp to-do id observed from two different connected accounts on
two different TimeTracker companies does not collide.

``basecamp_todolist_id`` is preserved (not part of the UNIQUE) so a
future v3.1 can surface list grouping without a schema migration.

Both FKs (``company_id``, ``task_id``) are ``ON DELETE CASCADE`` so
removing a company or task cleans up its mappings automatically.

Round-trips cleanly (upgrade -> downgrade -> upgrade).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "026_basecamp_task_mappings"
down_revision = "025_basecamp_target_team"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "basecamp_task_mappings",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("basecamp_account_id", sa.String(64), nullable=False),
        sa.Column("basecamp_project_id", sa.String(64), nullable=False),
        sa.Column("basecamp_todolist_id", sa.String(64), nullable=False),
        sa.Column("basecamp_todo_id", sa.String(64), nullable=False),
        sa.Column("task_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "last_synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "company_id",
            "basecamp_account_id",
            "basecamp_todo_id",
            name="uq_basecamp_task_mapping_external",
        ),
    )
    op.create_index(
        "ix_basecamp_task_mappings_company_id",
        "basecamp_task_mappings",
        ["company_id"],
    )
    op.create_index(
        "ix_basecamp_task_mappings_task_id",
        "basecamp_task_mappings",
        ["task_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_basecamp_task_mappings_task_id",
        table_name="basecamp_task_mappings",
    )
    op.drop_index(
        "ix_basecamp_task_mappings_company_id",
        table_name="basecamp_task_mappings",
    )
    op.drop_table("basecamp_task_mappings")
