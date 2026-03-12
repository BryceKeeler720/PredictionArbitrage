"""Add expires_at to arbitrage_opportunities.

Revision ID: 002
Revises: 001
Create Date: 2026-03-12
"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "arbitrage_opportunities",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("arbitrage_opportunities", "expires_at")
