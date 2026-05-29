"""Add anomaly_dismissals table for persisted admin dismissals.

Revision ID: 034_anomaly_dismissals
Revises: 033_bc_webhook_stale_fix
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "034_anomaly_dismissals"
down_revision = "033_bc_webhook_stale_fix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "anomaly_dismissals",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("target_user_id", sa.Integer(), nullable=False),
        sa.Column("anomaly_type", sa.String(length=64), nullable=False),
        sa.Column("dismissed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "dismissed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["target_user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["dismissed_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint(
            "company_id",
            "target_user_id",
            "anomaly_type",
            name="uq_anomaly_dismissals_company_user_type",
        ),
    )
    op.create_index(
        "ix_anomaly_dismissals_company_id",
        "anomaly_dismissals",
        ["company_id"],
    )
    op.create_index(
        "ix_anomaly_dismissals_target_user_id",
        "anomaly_dismissals",
        ["target_user_id"],
    )
    # Composite index supporting the filter-on-listing lookup
    # (WHERE company_id = :id, then build set of (target_user_id, anomaly_type)).
    op.create_index(
        "ix_anomaly_dismissals_company_user_type",
        "anomaly_dismissals",
        ["company_id", "target_user_id", "anomaly_type"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_anomaly_dismissals_company_user_type",
        table_name="anomaly_dismissals",
    )
    op.drop_index(
        "ix_anomaly_dismissals_target_user_id",
        table_name="anomaly_dismissals",
    )
    op.drop_index(
        "ix_anomaly_dismissals_company_id",
        table_name="anomaly_dismissals",
    )
    op.drop_table("anomaly_dismissals")
