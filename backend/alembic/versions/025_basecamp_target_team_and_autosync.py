"""Add target_team_id + auto_sync_enabled to basecamp_credentials

Revision ID: 025_basecamp_target_team
Revises: 024_long_timer_email
Create Date: 2026-05-11

Adds two columns supporting Basecamp integration v2:

* ``target_team_id`` (nullable FK -> teams.id, ON DELETE SET NULL).
  When set, mirrored projects are created in this team. When NULL the
  service falls back to the legacy behavior (lowest-id team for the
  company) so existing installs are byte-for-byte unchanged after
  migration.
* ``auto_sync_enabled`` (boolean NOT NULL DEFAULT FALSE). When TRUE the
  4-hourly ``scheduler-4hourly`` container runs the sync for this
  company. Opt-in; defaults to FALSE for every existing row.

Round-trips cleanly (upgrade -> downgrade -> upgrade).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "025_basecamp_target_team"
down_revision = "024_long_timer_email"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "basecamp_credentials",
        sa.Column("target_team_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "basecamp_credentials",
        sa.Column(
            "auto_sync_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_foreign_key(
        "fk_basecamp_credentials_target_team_id",
        "basecamp_credentials",
        "teams",
        ["target_team_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_basecamp_credentials_target_team_id",
        "basecamp_credentials",
        type_="foreignkey",
    )
    op.drop_column("basecamp_credentials", "auto_sync_enabled")
    op.drop_column("basecamp_credentials", "target_team_id")
