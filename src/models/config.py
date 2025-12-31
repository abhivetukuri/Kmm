"""Configuration models for soccer market making strategy."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

from kalshi_trader.types import MarketTicker


class League(str, Enum):
    """Supported soccer leagues."""

    EPL = "EPL"
    BUNDESLIGA = "Bundesliga"
    LA_LIGA = "La Liga"
    SERIE_A = "Serie A"
    LIGUE_1 = "Ligue 1"


class MarketArchetype(str, Enum):
    """Market contract archetype."""

    TWO_OUTCOME = "two_outcome"  # YES/NO
    THREE_OUTCOME = "three_outcome"  # Home/Draw/Away


class KalshiMarketConfig(BaseModel):
    """Kalshi market configuration."""

    env: Literal["demo", "prod"]
    ticker: str
    market_id: str | None = None
    yes_side_definition: str = ""


class PolymarketMarketConfig(BaseModel):
    """Polymarket market configuration."""

    market_slug: str
    token_ids: dict[str, str | None] = Field(default_factory=dict)  # home, draw, away
    outcome_definition: str = ""


class SettlementEquivalence(BaseModel):
    """Settlement equivalence validation."""

    rules_hash: str  # SHA256 of normalized settlement text
    notes: str = ""


class SoccerMarketConfig(BaseModel):
    """Configuration for a single soccer market."""

    id: str
    league: League
    match_name: str
    start_time_utc: datetime
    scheduled_end_time_utc: datetime
    kalshi: KalshiMarketConfig
    polymarket: PolymarketMarketConfig
    settlement_equivalence: SettlementEquivalence
    archetype: MarketArchetype = MarketArchetype.TWO_OUTCOME

    @field_validator("start_time_utc", "scheduled_end_time_utc", mode="before")
    @classmethod
    def parse_datetime(cls, v: str | datetime) -> datetime:
        """Parse ISO8601 datetime string."""
        if isinstance(v, datetime):
            return v
        return datetime.fromisoformat(v.replace("Z", "+00:00"))

    @property
    def kalshi_ticker(self) -> MarketTicker:
        """Get Kalshi ticker as typed."""
        return MarketTicker(self.kalshi.ticker)


class SoccerStrategyParams(BaseModel):
    """Strategy parameters for soccer market making."""

    # Fair price model
    w_poly_base_prematch: float = 0.70
    w_poly_base_inplay: float = 0.85
    poly_spread_narrow_threshold: float = 0.02
    poly_spread_wide_threshold: float = 0.06
    poly_spread_narrow_bonus: float = 0.05
    poly_spread_wide_penalty: float = 0.10
    shock_score_threshold: float = 3.0
    pause_seconds_shock: int = 10

    # Quoting
    base_half_spread_prematch: float = 0.03
    base_half_spread_inplay: float = 0.06
    adv_buffer_prematch: float = 0.01
    adv_buffer_inplay: float = 0.03
    adv_buffer_shock: float = 0.02
    repricing_tick_threshold_prematch: float = 0.02
    repricing_tick_threshold_inplay: float = 0.01
    min_seconds_between_writes_prematch: float = 0.5
    min_seconds_between_writes_inplay: float = 0.2

    # Order sizing
    max_order_notional_demo: float = 3.00
    max_order_notional_live: float = 1.00
    max_contracts_per_order_demo: int = 25
    max_contracts_per_order_live: int = 10
    max_size_vs_depth_ratio: float = 0.25

    # Risk limits
    max_position_notional_demo: float = 25.00
    max_position_notional_live: float = 10.00
    max_total_notional_demo: float = 125.00
    max_total_notional_live: float = 50.00
    max_filled_notional_per_minute_demo: float = 20.00
    max_filled_notional_per_minute_live: float = 8.00
    drawdown_limit_demo: float = 50.00
    drawdown_limit_live: float = 20.00

    # Match phase
    stop_before_end_seconds: int = 600  # 10 minutes

    # Data freshness
    stale_seconds_prematch: int = 10
    stale_seconds_inplay: int = 3
    warmup_seconds: int = 5

    # Polymarket polling
    poll_interval_prematch_ms: int = 2000
    poll_interval_inplay_ms: int = 500
    poll_interval_cooldown_ms: int = 250
    cooldown_duration_seconds: int = 10


class SoccerConfig(BaseModel):
    """Complete soccer market making configuration."""

    env: Literal["demo", "prod"]
    markets: list[SoccerMarketConfig]
    params: SoccerStrategyParams = Field(default_factory=SoccerStrategyParams)

    @classmethod
    def load(cls, config_path: str | Path) -> SoccerConfig:
        """Load configuration from YAML file."""
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path) as f:
            data = yaml.safe_load(f)

        # Load params from separate file if specified
        if "params_file" in data:
            params_path = path.parent / data["params_file"]
            with open(params_path) as pf:
                params_data = yaml.safe_load(pf)
                data["params"] = params_data

        return cls.model_validate(data)

    def validate_settlement_equivalence(self) -> None:
        """Validate that all markets have matching settlement rules."""
        for market in self.markets:
            # In production, this would check against stored rules_hash
            # For now, just ensure it's set
            if not market.settlement_equivalence.rules_hash:
                raise ValueError(f"Market {market.id} missing settlement rules_hash")

