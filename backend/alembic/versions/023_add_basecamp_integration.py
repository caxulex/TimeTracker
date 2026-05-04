"""Add Basecamp integration tables

Revision ID: 023_basecamp_integration
Revises: 022_company_overtime_cfg
Create Date: 2026-05-01

Adds two tables that support the v1 Basecamp -> TimeTracker one-way
project mirror:

* ``basecamp_credentials``
    Per-company OAuth credentials. Tokens are encrypted at rest with
    ``API_KEY_ENCRYPTION_KEY`` (AES-256-GCM via
    ``app.services.encryption_service``). Exactly one row per company
    (UNIQUE on ``company_id``); upserted on (re-)connect.

* ``basecamp_project_mappings``
    Maps a Basecamp project (``basecamp_account_id`` +
    ``basecamp_project_id``) to an internal ``projects.id`` row, so the
    sync method is idempotent: re-running it updates existing internal
    projects in place instead of creating duplicates. UNIQUE on the
    triple ``(company_id, basecamp_account_id, basecamp_project_id)``.

Round-trips cleanly (upgrade -> downgrade -> upgrade).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "023_basecamp_integration"
down_revision = "022_company_overtime_cfg"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "basecamp_credentials",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("account_id", sa.String(64), nullable=False),
        sa.Column("account_name", sa.String(255), nullable=True),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("connected_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["connected_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint("company_id", name="uq_basecamp_credentials_company_id"),
    )
    op.create_index(
        "ix_basecamp_credentials_company_id",
        "basecamp_credentials",
        ["company_id"],
    )

    op.create_table(
        "basecamp_project_mappings",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("basecamp_account_id", sa.String(64), nullable=False),
        sa.Column("basecamp_project_id", sa.String(64), nullable=False),
        sa.Column("internal_project_id", sa.BigInteger(), nullable=False),
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
            ["internal_project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "company_id",
            "basecamp_account_id",
            "basecamp_project_id",
            name="uq_basecamp_project_mapping_external",
        ),
    )
    op.create_index(
        "ix_basecamp_project_mappings_company_id",
        "basecamp_project_mappings",
        ["company_id"],
    )
    op.create_index(
        "ix_basecamp_project_mappings_internal_project_id",
        "basecamp_project_mappings",
        ["internal_project_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_basecamp_project_mappings_internal_project_id",
        table_name="basecamp_project_mappings",
    )
    op.drop_index(
        "ix_basecamp_project_mappings_company_id",
        table_name="basecamp_project_mappings",
    )
    op.drop_table("basecamp_project_mappings")

    op.drop_index(
        "ix_basecamp_credentials_company_id",
        table_name="basecamp_credentials",
    )
    op.drop_table("basecamp_credentials")
