import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db import Base


class ArbitrageOpportunity(Base):
    __tablename__ = "arbitrage_opportunities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False, default="cross_platform")

    # Leg details stored as JSON array
    legs: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)

    # Profit calculations
    total_cost: Mapped[float] = mapped_column(Float, nullable=False)
    guaranteed_profit: Mapped[float] = mapped_column(Float, nullable=False)
    profit_after_fees: Mapped[float] = mapped_column(Float, nullable=False)
    profit_pct: Mapped[float] = mapped_column(Float, nullable=False)
    max_size_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Status
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Human-readable summary
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
