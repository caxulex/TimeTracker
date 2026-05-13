"""Relax tasks.name from VARCHAR(255) to TEXT

Revision ID: 028_tasks_name_text
Revises: 027_bc_task_mapping_metadata
Create Date: 2026-05-13

Retires the 255-byte truncation workaround introduced in v3.0.2
(``_truncate_task_name`` in ``basecamp_service``). Basecamp to-do
titles can legitimately exceed 255 characters; truncating them at the
DB boundary lost information in the timer dropdown and reports.

PostgreSQL stores ``TEXT`` and ``VARCHAR(n)`` in the same on-disk
representation, so this ``ALTER TYPE`` runs as a metadata-only change
without a table rewrite -- safe on the production ``tasks`` table.

Down-migration uses a ``USING substring(name, 1, 255)`` clause so that
if the downgrade ever runs after rows longer than 255 chars have been
written, the rollback still succeeds (with the same truncation the old
code performed at the application layer).
"""
from alembic import op


# revision identifiers, used by Alembic.
# Kept under 32 chars to fit ``alembic_version.version_num``
# VARCHAR(32) without overflowing.
revision = "028_tasks_name_text"
down_revision = "027_bc_task_mapping_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE tasks ALTER COLUMN name TYPE TEXT")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE tasks ALTER COLUMN name TYPE VARCHAR(255) "
        "USING substring(name, 1, 255)"
    )
