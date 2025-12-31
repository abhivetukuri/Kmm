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
    
    @property
    def yes_price(self) -> float:
        """Get yes price (midpoint of bid/ask)."""
        if self.yes_ask is not None and self.yes_bid is not None:
            return (self.yes_ask + self.yes_bid) / 2
        elif self.yes_ask is not None:
            return self.yes_ask
        elif self.yes_bid is not None:
            return self.yes_bid
        else:
            return 0.5  # Default
    
    @property 
    def no_price(self) -> float:
        """Get no price (midpoint of bid/ask)."""
        if self.no_ask is not None and self.no_bid is not None:
            return (self.no_ask + self.no_bid) / 2
        elif self.no_ask is not None:
            return self.no_ask
        elif self.no_bid is not None:
            return self.no_bid
        else:
            return 0.5  # Default


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
    confidence: float  # 0.0 to 1.0 (renamed for consistency)
    match_reason: str
    settlement_notes: str
    
    @property
    def match_confidence(self) -> float:
        """Backward compatibility."""
        return self.confidence