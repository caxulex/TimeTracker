"""Normalize company subscription_tier values to free/standard/unlimited.

This migration introduces a strict CHECK constraint for ``companies.subscription_tier``
with allowed values: ``free``, ``standard``, ``unlimited``.

Upgrade behavior:
- Abort if unexpected legacy values exist before any rewrite.
- Rewrite known legacy values (professional/enterprise/trial) to free.
- Set column default to free.
- Add CHECK constraint.

Downgrade behavior:
- Drops CHECK constraint and restores default to trial.
- Does not restore original per-row tier strings because information is lossy
  after normalization to free.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "042_tier_values"
down_revision = "041_add_stripe_ids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    unexpected = bind.execute(
        sa.text(
            """
            SELECT DISTINCT subscription_tier
            FROM companies
            WHERE subscription_tier NOT IN ('professional', 'enterprise', 'trial', 'free')
            ORDER BY subscription_tier
            """
        )
    ).fetchall()

    if unexpected:
        values = ", ".join(row[0] for row in unexpected)
        raise RuntimeError(
            "Unexpected companies.subscription_tier values found; aborting migration: "
            f"{values}"
        )

    op.execute(
        sa.text(
            """
            UPDATE companies
            SET subscription_tier = 'free'
            WHERE subscription_tier IN ('professional', 'enterprise', 'trial')
            """
        )
    )

    op.alter_column(
        "companies",
        "subscription_tier",
        existing_type=sa.String(length=50),
        existing_nullable=False,
        server_default="free",
    )

    op.create_check_constraint(
        "ck_companies_subscription_tier",
        "companies",
        "subscription_tier IN ('free', 'standard', 'unlimited')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_companies_subscription_tier", "companies", type_="check")

    op.alter_column(
        "companies",
        "subscription_tier",
        existing_type=sa.String(length=50),
        existing_nullable=False,
        server_default="trial",
    )
