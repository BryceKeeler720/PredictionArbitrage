import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)


@dataclass
class MarketData:
    """Intermediate data structure returned by collectors before DB persistence."""

    platform: str
    platform_id: str
    title: str
    slug: str = ""
    category: str = "unknown"
    yes_price: float = 0.0
    no_price: float = 0.0
    yes_ask: float | None = None
    yes_bid: float | None = None
    no_ask: float | None = None
    no_bid: float | None = None
    volume_24h: float = 0.0
    liquidity: float = 0.0
    open_interest: float | None = None
    close_time: datetime | None = None
    source_url: str = ""
    raw_data: dict = field(default_factory=dict)


class BaseCollector(ABC):
    """Abstract base class for all platform collectors."""

    platform_name: str
    base_url: str

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                headers={"User-Agent": "PredArb/0.1"},
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    @abstractmethod
    async def fetch_markets(self) -> list[MarketData]:
        """Fetch all active markets from the platform."""
        ...

    @abstractmethod
    async def fetch_prices(self, market_ids: list[str]) -> dict[str, MarketData]:
        """Fetch updated prices for specific markets. Returns {platform_id: MarketData}."""
        ...

    async def _get(self, url: str, params: dict | None = None) -> dict | list:
        """Make a GET request with basic error handling."""
        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} platform={self.platform_name}>"
