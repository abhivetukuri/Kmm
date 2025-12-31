"""Core types for the soccer market maker."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class KalshiMarket:
    """Kalshi market information."""
    
    ticker: str
    title: str
    subtitle: str | None
    category: str
    status: str
    yes_ask: float | None
    yes_bid: float | None
    no_ask: float | None  
    no_bid: float | None
    open_time: datetime | None
    close_time: datetime | None
    settle_time: datetime | None
    raw_data: dict[str, Any]


@dataclass
class PolymarketMarket:
    """Polymarket market information."""
    
    condition_id: str
    market_slug: str
    question: str
    description: str | None
    category: str
    end_date_iso: datetime | None
    outcomes: list[str]
    outcome_prices: list[float]
    tokens: list[PolymarketToken]
    raw_data: dict[str, Any]


@dataclass
class PolymarketToken:
    """Polymarket outcome token."""
    
    token_id: str
    outcome: str
    price: float | None
    win_index: int


@dataclass  
class MatchedMarket:
    """A matched market between Kalshi and Polymarket."""
    
    kalshi_market: KalshiMarket
    polymarket_market: PolymarketMarket
    match_confidence: float  # 0.0 to 1.0
    match_reason: str
    settlement_notes: str