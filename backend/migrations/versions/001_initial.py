"""Initial schema.

Revision ID: 001
Revises:
Create Date: 2026-03-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "normalized_markets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("platform_id", sa.String(255), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("slug", sa.String(500), nullable=False, server_default=""),
        sa.Column("category", sa.String(100), nullable=False, server_default="unknown"),
        sa.Column("yes_price", sa.Float, nullable=False, server_default="0"),
        sa.Column("no_price", sa.Float, nullable=False, server_default="0"),
        sa.Column("yes_ask", sa.Float, nullable=True),
        sa.Column("yes_bid", sa.Float, nullable=True),
        sa.Column("no_ask", sa.Float, nullable=True),
        sa.Column("no_bid", sa.Float, nullable=True),
        sa.Column("volume_24h", sa.Float, nullable=False, server_default="0"),
        sa.Column("liquidity", sa.Float, nullable=False, server_default="0"),
        sa.Column("open_interest", sa.Float, nullable=True),
        sa.Column("close_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("source_url", sa.Text, nullable=False, server_default=""),
        sa.Column("raw_data", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
        sa.UniqueConstraint("platform", "platform_id", name="uq_platform_market"),
    )
    op.create_index("ix_market_platform", "normalized_markets", ["platform"])
    op.create_index("ix_market_category", "normalized_markets", ["category"])
    op.create_index("ix_market_close_time", "normalized_markets", ["close_time"])

    op.create_table(
        "market_matches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("canonical_question", sa.Text, nullable=False),
        sa.Column("match_confidence", sa.Float, nullable=False, server_default="0"),
        sa.Column("match_method", sa.String(50), nullable=False, server_default="auto_fuzzy"),
        sa.Column("verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "market_match_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("match_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("market_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.UniqueConstraint("match_id", "market_id", name="uq_match_market"),
    )
    op.create_index("ix_match_members_match_id", "market_match_members", ["match_id"])
    op.create_index("ix_match_members_market_id", "market_match_members", ["market_id"])

    op.create_table(
        "market_match_overrides",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("platform_a", sa.String(50), nullable=False),
        sa.Column("market_id_a", sa.String(255), nullable=False),
        sa.Column("platform_b", sa.String(50), nullable=False),
        sa.Column("market_id_b", sa.String(255), nullable=False),
        sa.Column("canonical_question", sa.Text, nullable=True),
        sa.Column("created_by", sa.String(100), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "arbitrage_opportunities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("match_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(50), nullable=False, server_default="cross_platform"),
        sa.Column("legs", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("total_cost", sa.Float, nullable=False),
        sa.Column("guaranteed_profit", sa.Float, nullable=False),
        sa.Column("profit_after_fees", sa.Float, nullable=False),
        sa.Column("profit_pct", sa.Float, nullable=False),
        sa.Column("max_size_usd", sa.Float, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
    )
    op.create_index("ix_arb_match_id", "arbitrage_opportunities", ["match_id"])


def downgrade() -> None:
    op.drop_table("arbitrage_opportunities")
    op.drop_table("market_match_overrides")
    op.drop_table("market_match_members")
    op.drop_table("market_matches")
    op.drop_table("normalized_markets")
