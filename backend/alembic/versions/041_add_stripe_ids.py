"""Add Stripe linkage IDs to companies.

Revision ID: 041_add_stripe_ids
Revises: 040_add_working_days
Create Date: 2026-06-29
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "041_add_stripe_ids"
down_revision = "040_add_working_days"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "companies",
        sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_companies_stripe_customer_id",
        "companies",
        ["stripe_customer_id"],
        unique=False,
    )
    op.create_index(
        "ix_companies_stripe_subscription_id",
        "companies",
        ["stripe_subscription_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_companies_stripe_subscription_id", table_name="companies")
    op.drop_index("ix_companies_stripe_customer_id", table_name="companies")
    op.drop_column("companies", "stripe_subscription_id")
    op.drop_column("companies", "stripe_customer_id")
