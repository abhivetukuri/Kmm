"""Market data store combining Kalshi and Polymarket data."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from kalshi_trader.soccer.polymarket_client import PolymarketMarketData, PolymarketTokenData
from kalshi_trader.types import MarketTicker, TopOfBook
from kalshi_trader.util.time import current_epoch_ms

logger = logging.getLogger(__name__)


@dataclass
class MarketSnapshot:
    """Combined market snapshot from Kalshi and Polymarket."""

    timestamp_ms: int
    market_id: str

    # Kalshi data
    kalshi_best_bid_price: float | None  # Probability 0.01-0.99
    kalshi_best_bid_size: int | None
    kalshi_best_ask_price: float | None
    kalshi_best_ask_size: int | None
    kalshi_mid: float | None
    kalshi_last_trade_price: float | None
    kalshi_stale: bool = False

    # Polymarket data
    polymarket_best_bid: float | None  # Probability 0.0-1.0
    polymarket_best_ask: float | None
    polymarket_mid: float | None
    polymarket_spread: float | None
    polymarket_top_depth_bid: float | None
    polymarket_top_depth_ask: float | None
    polymarket_stale: bool = False

    # Data quality flags
    data_staleness_flags: dict[str, bool] = field(default_factory=dict)


class MarketDataStore:
    """Stores and manages market data snapshots."""

    def __init__(self, stale_seconds_prematch: int = 10, stale_seconds_inplay: int = 3):
        """Initialize store.

        Args:
            stale_seconds_prematch: Seconds before data is considered stale pre-match
            stale_seconds_inplay: Seconds before data is considered stale in-play
        """
        self._stale_seconds_prematch = stale_seconds_prematch
        self._stale_seconds_inplay = stale_seconds_inplay
        self._snapshots: dict[str, MarketSnapshot] = {}

    def update_kalshi(
        self,
        market_id: str,
        ticker: MarketTicker,
        tob: TopOfBook | None,
        match_phase: str,
    ) -> MarketSnapshot:
        """Update Kalshi data for a market.

        Args:
            market_id: Market ID
            ticker: Market ticker
            tob: Top of book data
            match_phase: Match phase ("PREMATCH" or "INPLAY")

        Returns:
            Updated snapshot
        """
        snapshot = self._snapshots.get(market_id)
        if snapshot is None:
            snapshot = MarketSnapshot(
                timestamp_ms=current_epoch_ms(),
                market_id=market_id,
                kalshi_best_bid_price=None,
                kalshi_best_bid_size=None,
                kalshi_best_ask_price=None,
                kalshi_best_ask_size=None,
                kalshi_mid=None,
                kalshi_last_trade_price=None,
            )

        now_ms = current_epoch_ms()

        if tob is not None:
            # Convert from ticks (1-99) to probability (0.01-0.99)
            snapshot.kalshi_best_bid_price = (
                int(tob.yes_best_price) / 100.0 if tob.yes_best_price else None
            )
            snapshot.kalshi_best_bid_size = int(tob.yes_best_qty) if tob.yes_best_qty else None
            snapshot.kalshi_best_ask_price = (
                int(tob.no_best_price) / 100.0 if tob.no_best_price else None
            )
            snapshot.kalshi_best_ask_size = int(tob.no_best_qty) if tob.no_best_qty else None

            # Calculate mid
            if snapshot.kalshi_best_bid_price and snapshot.kalshi_best_ask_price:
                snapshot.kalshi_mid = (
                    snapshot.kalshi_best_bid_price + snapshot.kalshi_best_ask_price
                ) / 2.0
            elif snapshot.kalshi_best_bid_price:
                snapshot.kalshi_mid = snapshot.kalshi_best_bid_price
            elif snapshot.kalshi_best_ask_price:
                snapshot.kalshi_mid = snapshot.kalshi_best_ask_price
            else:
                snapshot.kalshi_mid = None

            snapshot.timestamp_ms = now_ms
            snapshot.kalshi_stale = False
        else:
            snapshot.kalshi_stale = self._is_stale(now_ms, snapshot.timestamp_ms, match_phase)

        self._snapshots[market_id] = snapshot
        return snapshot

    def update_polymarket(
        self,
        market_id: str,
        poly_data: PolymarketMarketData | None,
        token_id: str,
        match_phase: str,
    ) -> MarketSnapshot:
        """Update Polymarket data for a market.

        Args:
            market_id: Market ID
            poly_data: Polymarket market data
            token_id: Token ID to use (for two-outcome markets)
            match_phase: Match phase

        Returns:
            Updated snapshot
        """
        snapshot = self._snapshots.get(market_id)
        if snapshot is None:
            snapshot = MarketSnapshot(
                timestamp_ms=current_epoch_ms(),
                market_id=market_id,
                kalshi_best_bid_price=None,
                kalshi_best_bid_size=None,
                kalshi_best_ask_price=None,
                kalshi_best_ask_size=None,
                kalshi_mid=None,
                kalshi_last_trade_price=None,
            )

        now_ms = current_epoch_ms()

        if poly_data and token_id in poly_data.tokens:
            token = poly_data.tokens[token_id]
            snapshot.polymarket_best_bid = token.best_bid
            snapshot.polymarket_best_ask = token.best_ask
            snapshot.polymarket_top_depth_bid = token.best_bid_size
            snapshot.polymarket_top_depth_ask = token.best_ask_size

            # Calculate mid and spread
            if token.best_bid is not None and token.best_ask is not None:
                snapshot.polymarket_mid = (token.best_bid + token.best_ask) / 2.0
                snapshot.polymarket_spread = token.best_ask - token.best_bid
            elif token.best_bid is not None:
                snapshot.polymarket_mid = token.best_bid
                snapshot.polymarket_spread = None
            elif token.best_ask is not None:
                snapshot.polymarket_mid = token.best_ask
                snapshot.polymarket_spread = None
            else:
                snapshot.polymarket_mid = None
                snapshot.polymarket_spread = None

            snapshot.timestamp_ms = max(snapshot.timestamp_ms, poly_data.timestamp_ms)
            snapshot.polymarket_stale = False
        else:
            snapshot.polymarket_stale = self._is_stale(now_ms, snapshot.timestamp_ms, match_phase)

        self._snapshots[market_id] = snapshot
        return snapshot

    def get_snapshot(self, market_id: str) -> MarketSnapshot | None:
        """Get current snapshot for a market."""
        return self._snapshots.get(market_id)

    def _is_stale(self, now_ms: int, data_ts_ms: int, match_phase: str) -> bool:
        """Check if data is stale."""
        stale_seconds = (
            self._stale_seconds_inplay if match_phase == "INPLAY" else self._stale_seconds_prematch
        )
        age_seconds = (now_ms - data_ts_ms) / 1000.0
        return age_seconds > stale_seconds

