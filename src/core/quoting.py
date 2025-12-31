"""Quoting engine for calculating bid/ask prices and sizes."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from kalshi_trader.soccer.fair_price import FairPriceOutput
from kalshi_trader.soccer.fee_model import fee_buffer_probability
from kalshi_trader.soccer.market_data_store import MarketSnapshot
from kalshi_trader.types import PriceTicks, Quantity

logger = logging.getLogger(__name__)


@dataclass
class Quote:
    """Desired quote (bid or ask)."""

    price: PriceTicks
    qty: Quantity


@dataclass
class QuotingOutput:
    """Output of quoting calculation."""

    bid: Quote | None
    ask: Quote | None
    reason: str = ""


class QuotingEngine:
    """Calculates bid/ask quotes based on fair price and risk parameters."""

    def __init__(
        self,
        base_half_spread_prematch: float = 0.03,
        base_half_spread_inplay: float = 0.06,
        adv_buffer_prematch: float = 0.01,
        adv_buffer_inplay: float = 0.03,
        adv_buffer_shock: float = 0.02,
        max_order_notional_demo: float = 3.00,
        max_order_notional_live: float = 1.00,
        max_contracts_per_order_demo: int = 25,
        max_contracts_per_order_live: int = 10,
        max_size_vs_depth_ratio: float = 0.25,
        is_demo: bool = True,
    ):
        """Initialize quoting engine.

        Args:
            base_half_spread_prematch: Base half-spread pre-match
            base_half_spread_inplay: Base half-spread in-play
            adv_buffer_prematch: Adverse selection buffer pre-match
            adv_buffer_inplay: Adverse selection buffer in-play
            adv_buffer_shock: Additional buffer during shock
            max_order_notional_demo: Max order notional in demo ($)
            max_order_notional_live: Max order notional in live ($)
            max_contracts_per_order_demo: Max contracts per order in demo
            max_contracts_per_order_live: Max contracts per order in live
            max_size_vs_depth_ratio: Max size as ratio of visible depth
            is_demo: Whether running in demo mode
        """
        self._base_half_spread_prematch = base_half_spread_prematch
        self._base_half_spread_inplay = base_half_spread_inplay
        self._adv_buffer_prematch = adv_buffer_prematch
        self._adv_buffer_inplay = adv_buffer_inplay
        self._adv_buffer_shock = adv_buffer_shock
        self._max_order_notional = max_order_notional_demo if is_demo else max_order_notional_live
        self._max_contracts_per_order = (
            max_contracts_per_order_demo if is_demo else max_contracts_per_order_live
        )
        self._max_size_vs_depth_ratio = max_size_vs_depth_ratio
        self._is_demo = is_demo

    def calculate_quotes(
        self,
        fair_output: FairPriceOutput,
        snapshot: MarketSnapshot,
        match_phase: str,
        current_bid_price: PriceTicks | None = None,
        current_ask_price: PriceTicks | None = None,
    ) -> QuotingOutput:
        """Calculate desired bid/ask quotes.

        Args:
            fair_output: Fair price calculation output
            snapshot: Market snapshot
            match_phase: Match phase ("PREMATCH" or "INPLAY")
            current_bid_price: Current resting bid price (if any)
            current_ask_price: Current resting ask price (if any)

        Returns:
            Quoting output with bid/ask quotes
        """
        # Check if we should quote
        if fair_output.is_shocked:
            return QuotingOutput(bid=None, ask=None, reason="shock_detected")

        if snapshot.kalshi_stale and snapshot.polymarket_stale:
            return QuotingOutput(bid=None, ask=None, reason="data_stale")

        # Calculate half-spread
        half_spread = self._calculate_half_spread(fair_output, match_phase, snapshot)

        # Calculate quote prices
        fair_prob = fair_output.fair
        bid_prob = fair_prob - half_spread
        ask_prob = fair_prob + half_spread

        # Convert to ticks and clamp
        bid_ticks = self._prob_to_ticks(bid_prob)
        ask_ticks = self._prob_to_ticks(ask_prob)

        # Post-only guards (don't cross the book)
        if snapshot.kalshi_best_ask_price:
            best_ask_ticks = self._prob_to_ticks(snapshot.kalshi_best_ask_price)
            if bid_ticks >= best_ask_ticks:
                bid_ticks = max(1, best_ask_ticks - 1)

        if snapshot.kalshi_best_bid_price:
            best_bid_ticks = self._prob_to_ticks(snapshot.kalshi_best_bid_price)
            if ask_ticks <= best_bid_ticks:
                ask_ticks = min(99, best_bid_ticks + 1)

        # Ensure bid <= ask - 0.02
        if bid_ticks >= ask_ticks - 2:
            # Widen spread
            mid_ticks = (bid_ticks + ask_ticks) // 2
            bid_ticks = max(1, mid_ticks - int(half_spread * 100))
            ask_ticks = min(99, mid_ticks + int(half_spread * 100))

        # Calculate sizes
        bid_qty = self._calculate_size(bid_ticks, snapshot.kalshi_best_bid_size, "bid")
        ask_qty = self._calculate_size(ask_ticks, snapshot.kalshi_best_ask_size, "ask")

        # Only quote if we have valid prices and sizes
        if bid_ticks < 1 or bid_ticks > 98 or bid_qty < 1:
            bid = None
        else:
            bid = Quote(price=PriceTicks(bid_ticks), qty=Quantity(bid_qty))

        if ask_ticks < 2 or ask_ticks > 99 or ask_qty < 1:
            ask = None
        else:
            ask = Quote(price=PriceTicks(ask_ticks), qty=Quantity(ask_qty))

        return QuotingOutput(bid=bid, ask=ask, reason="ok")

    def _calculate_half_spread(
        self,
        fair_output: FairPriceOutput,
        match_phase: str,
        snapshot: MarketSnapshot,
    ) -> float:
        """Calculate half-spread."""
        # Base half-spread
        if match_phase == "INPLAY":
            half_spread = self._base_half_spread_inplay
            adv_buffer = self._adv_buffer_inplay
        else:
            half_spread = self._base_half_spread_prematch
            adv_buffer = self._adv_buffer_prematch

        # Adverse selection buffer
        half_spread += adv_buffer

        # Shock buffer
        if fair_output.shock_score > 1.0:
            half_spread += self._adv_buffer_shock

        # Fee buffer
        # Use fair price as estimate for fee calculation
        fair_ticks = self._prob_to_ticks(fair_output.fair)
        fee_buffer = fee_buffer_probability(PriceTicks(fair_ticks))
        half_spread += fee_buffer

        return half_spread

    def _calculate_size(
        self,
        price_ticks: int,
        visible_depth: int | None,
        side: str,
    ) -> int:
        """Calculate order size.

        Args:
            price_ticks: Price in ticks
            visible_depth: Visible depth on that side
            side: "bid" or "ask"

        Returns:
            Order size in contracts
        """
        # Convert price to probability for notional calculation
        price_prob = price_ticks / 100.0

        # Calculate max contracts from notional
        max_contracts_notional = int(self._max_order_notional / max(0.01, price_prob))
        max_contracts = min(max_contracts_notional, self._max_contracts_per_order)

        # Cap relative to visible depth
        if visible_depth:
            max_contracts_depth = max(1, int(visible_depth * self._max_size_vs_depth_ratio))
            max_contracts = min(max_contracts, max_contracts_depth)

        # Ensure at least 1 contract
        return max(1, max_contracts)

    def _prob_to_ticks(self, prob: float) -> int:
        """Convert probability (0.0-1.0) to ticks (1-99)."""
        ticks = int(round(prob * 100))
        return max(1, min(99, ticks))

