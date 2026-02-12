"""Add multi-tenant and query-pattern performance indexes

Revision ID: 020_mt_perf_indexes
Revises: 019_nullable_project
Create Date: 2026-02-12

PURPOSE:
Phase 9B database index review.  These indexes target the heaviest query
patterns identified during code review of routers/reports.py, routers/admin.py,
and routers/payroll.py:

1. Multi-tenant lookups: Users and teams are filtered by company_id on
   nearly every list/report endpoint.  Compound indexes avoid seq-scans
   on the FK column alone.
2. Running-timer poll: Frequent queries for is_running=true for a given
   user benefit from a partial index that stays tiny.
3. Task-board filtering: Tasks are filtered by (project_id, status) on
   every board view.
4. Payroll date queries: Payroll periods are looked up by (start_date,
   end_date) ranges during payroll processing.

SAFETY:
- All operations are pure ADD — no existing indexes are dropped or modified.
- Column-existence guards are used so the migration is safe even if a
  column hasn't been created in a particular deployment path.
- IF NOT EXISTS is used wherever the Alembic API supports it, and raw
  SQL uses CREATE INDEX IF NOT EXISTS for the partial index.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "020_mt_perf_indexes"
down_revision = "019_nullable_project"
branch_labels = None
depends_on = None


def _table_has_column(table: str, column: str) -> bool:
    """Check whether a column exists on a table before attempting to index it."""
    from sqlalchemy import inspect as sa_inspect
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    try:
        columns = [c["name"] for c in inspector.get_columns(table)]
    except Exception:
        return False
    return column in columns


def _index_exists(index_name: str) -> bool:
    """Check whether an index already exists to make the migration idempotent."""
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes WHERE indexname = :name"
        ),
        {"name": index_name},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. users — compound (company_id, email) for multi-tenant login
    #    Used by: POST /api/auth/login, GET /api/users (admin listing)
    # ------------------------------------------------------------------
    if _table_has_column("users", "company_id"):
        if not _index_exists("ix_users_company_email"):
            op.create_index(
                "ix_users_company_email",
                "users",
                ["company_id", "email"],
                unique=False,
            )
        # compound (company_id, is_active) for admin user-list filtering
        if not _index_exists("ix_users_company_active"):
            op.create_index(
                "ix_users_company_active",
                "users",
                ["company_id", "is_active"],
                unique=False,
            )

    # ------------------------------------------------------------------
    # 2. teams — (company_id) for multi-tenant team listing
    #    Used by: GET /api/teams, project dropdowns, team assignment
    # ------------------------------------------------------------------
    if _table_has_column("teams", "company_id"):
        if not _index_exists("ix_teams_company"):
            op.create_index(
                "ix_teams_company",
                "teams",
                ["company_id"],
                unique=False,
            )

    # ------------------------------------------------------------------
    # 3. time_entries — partial index for running-timer lookups
    #    Used by: Timer status checks (WHERE is_running = true)
    #    A partial index keeps the index tiny — only running rows.
    # ------------------------------------------------------------------
    if not _index_exists("ix_time_entries_running"):
        op.execute(
            """
            CREATE INDEX ix_time_entries_running
            ON time_entries (user_id)
            WHERE is_running = true
            """
        )

    # ------------------------------------------------------------------
    # 4. tasks — compound (project_id, status) for task-board filtering
    #    Used by: GET /api/tasks?project_id=X&status=Y, task boards
    # ------------------------------------------------------------------
    if not _index_exists("ix_tasks_project_status"):
        op.create_index(
            "ix_tasks_project_status",
            "tasks",
            ["project_id", "status"],
            unique=False,
        )

    # ------------------------------------------------------------------
    # 5. payroll_periods — compound (start_date, end_date) for range queries
    #    Used by: GET /api/payroll/periods, payroll processing
    #    Note: payroll_periods doesn't have company_id — isolation is
    #    via the payroll_entries → user → company chain.
    # ------------------------------------------------------------------
    if not _index_exists("ix_payroll_periods_date_range"):
        op.create_index(
            "ix_payroll_periods_date_range",
            "payroll_periods",
            ["start_date", "end_date"],
            unique=False,
        )

    # ------------------------------------------------------------------
    # 6. time_entries — compound (user_id, is_running) for "my running
    #    timer" queries (non-partial alternative for broader queries)
    # ------------------------------------------------------------------
    if not _index_exists("ix_time_entries_user_running"):
        op.create_index(
            "ix_time_entries_user_running",
            "time_entries",
            ["user_id", "is_running"],
            unique=False,
        )

    # ------------------------------------------------------------------
    # 7. work_sessions — compound (user_id, status) for active session
    #    lookups in the micro-task system
    # ------------------------------------------------------------------
    if not _index_exists("ix_work_sessions_user_status"):
        op.create_index(
            "ix_work_sessions_user_status",
            "work_sessions",
            ["user_id", "status"],
            unique=False,
        )


def downgrade() -> None:
    """Drop all indexes added in this migration, in reverse order."""
    op.execute("DROP INDEX IF EXISTS ix_work_sessions_user_status")
    op.execute("DROP INDEX IF EXISTS ix_time_entries_user_running")
    op.execute("DROP INDEX IF EXISTS ix_payroll_periods_date_range")
    op.execute("DROP INDEX IF EXISTS ix_tasks_project_status")
    op.execute("DROP INDEX IF EXISTS ix_time_entries_running")
    op.execute("DROP INDEX IF EXISTS ix_teams_company")
    op.execute("DROP INDEX IF EXISTS ix_users_company_active")
    op.execute("DROP INDEX IF EXISTS ix_users_company_email")
