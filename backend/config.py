from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # Database
    database_url: str = "postgresql+asyncpg://predarb:changeme@localhost:5433/predarb"
    redis_url: str = "redis://localhost:6380/0"

    # Polling
    poll_interval_seconds: int = 60
    price_refresh_seconds: int = 30

    # Thresholds
    min_profit_pct: float = 1.0
    min_profit_usd: float = 0.50
    min_liquidity_usd: float = 50.0
    max_time_to_close_days: int = 365
    min_volume_24h: float = 100.0

    # Matching
    match_confidence_threshold: float = 0.40
    auto_verify_threshold: float = 0.80

    # Alerts
    alert_cooldown_minutes: int = 30
    daily_digest_hour: int = 8
    discord_webhook_low: str = ""
    discord_webhook_medium: str = ""
    discord_webhook_high: str = ""

    # Platform keys (Phase 4 — trading only)
    kalshi_api_key: str = ""
    kalshi_api_secret: str = ""
    polymarket_private_key: str = ""

    # App
    log_level: str = "INFO"


settings = Settings()
