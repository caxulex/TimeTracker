"""Add API key health tracking fields.

Revision ID: 037_api_keys_health_tracking
Revises: 036_project_teams_assoc
Create Date: 2026-06-04
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "037_api_keys_health_tracking"
down_revision = "036_project_teams_assoc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column("last_successful_call_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "api_keys",
        sa.Column("last_failed_call_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "api_keys",
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "api_keys",
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "api_keys",
        sa.Column("last_error_message", sa.Text(), nullable=True),
    )
    op.add_column(
        "api_keys",
        sa.Column("last_error_status_code", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("api_keys", "last_error_status_code")
    op.drop_column("api_keys", "last_error_message")
    op.drop_column("api_keys", "failure_count")
    op.drop_column("api_keys", "success_count")
    op.drop_column("api_keys", "last_failed_call_at")
    op.drop_column("api_keys", "last_successful_call_at")
