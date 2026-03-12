import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db import Base


class NormalizedMarket(Base):
    __tablename__ = "normalized_markets"
    __table_args__ = (
        UniqueConstraint("platform", "platform_id", name="uq_platform_market"),
        Index("ix_market_platform", "platform"),
        Index("ix_market_category", "category"),
        Index("ix_market_close_time", "close_time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    platform_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="unknown")

    # Prices (0.0 - 1.0)
    yes_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    no_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    yes_ask: Mapped[float | None] = mapped_column(Float, nullable=True)
    yes_bid: Mapped[float | None] = mapped_column(Float, nullable=True)
    no_ask: Mapped[float | None] = mapped_column(Float, nullable=True)
    no_bid: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Market metrics
    volume_24h: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    liquidity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    open_interest: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Metadata
    close_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    active: Mapped[bool] = mapped_column(nullable=False, default=True)


class MarketMatch(Base):
    __tablename__ = "market_matches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_question: Mapped[str] = mapped_column(Text, nullable=False)
    match_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    match_method: Mapped[str] = mapped_column(String(50), nullable=False, default="auto_fuzzy")
    verified: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class MarketMatchMember(Base):
    """Links NormalizedMarkets to MarketMatches (many-to-many)."""

    __tablename__ = "market_match_members"
    __table_args__ = (
        UniqueConstraint("match_id", "market_id", name="uq_match_market"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    market_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)


class MarketMatchOverride(Base):
    __tablename__ = "market_match_overrides"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform_a: Mapped[str] = mapped_column(String(50), nullable=False)
    market_id_a: Mapped[str] = mapped_column(String(255), nullable=False)
    platform_b: Mapped[str] = mapped_column(String(50), nullable=False)
    market_id_b: Mapped[str] = mapped_column(String(255), nullable=False)
    canonical_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
