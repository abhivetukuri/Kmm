"""Kalshi fee model for calculating trading fees."""

from __future__ import annotations

import logging
from typing import Literal

from kalshi_trader.types import Cents, PriceTicks, Quantity

logger = logging.getLogger(__name__)


def kalshi_fee_cents(
    price: PriceTicks,
    contracts: Quantity,
    market_category: str = "default",
) -> Cents:
    """Calculate Kalshi taker fee in cents for an order.

    This is a conservative upper bound estimate based on Kalshi's fee schedule.
    Actual fees depend on:
    - Market category (sports, politics, etc.)
    - Price level (fees are percentage-based with rounding)
    - Maker vs taker (we assume taker for worst case)

    Args:
        price: Order price in ticks (cents), 1-99
        contracts: Number of contracts
        market_category: Market category (default, sports, politics, etc.)

    Returns:
        Fee in cents (upper bound estimate)
    """
    # Kalshi fee structure (simplified):
    # - Taker fees: typically 5-10% of notional with minimums
    # - Maker fees: typically 0-2% or rebates
    # - Fees are rounded up

    # Conservative estimate: 10% taker fee
    # This is intentionally high to ensure we don't underestimate
    notional_cents = int(price) * int(contracts)
    fee_percent = 0.10  # 10% taker fee (worst case)

    fee_cents = int(notional_cents * fee_percent)

    # Minimum fee (typically $0.01 per contract or $0.10 minimum)
    min_fee_cents = max(10, int(contracts))  # $0.10 or $0.01 per contract

    # Round up to nearest cent
    fee_cents = max(fee_cents, min_fee_cents)

    logger.debug(
        "Fee calculation: price=%d, contracts=%d, notional=%d, fee=%d",
        int(price),
        int(contracts),
        notional_cents,
        fee_cents,
    )

    return Cents(fee_cents)


def fee_buffer_probability(price: PriceTicks, market_category: str = "default") -> float:
    """Calculate fee buffer as a probability (0.0-1.0).

    This is used to widen spreads to account for fees.

    Args:
        price: Order price in ticks
        market_category: Market category

    Returns:
        Fee buffer as probability (e.g., 0.02 = 2%)
    """
    # Calculate fee per contract
    fee_per_contract_cents = kalshi_fee_cents(price, Quantity(1), market_category)
    fee_per_contract = int(fee_per_contract_cents) / 100.0

    # Fee buffer is 2x the fee per contract (conservative)
    fee_buffer = max(0.01, 2 * fee_per_contract)

    # Convert to probability (already in probability space since price is 0.01-0.99)
    return min(0.10, fee_buffer)  # Cap at 10%


def effective_spread_after_fees(
    bid_price: PriceTicks,
    ask_price: PriceTicks,
    contracts: Quantity,
    market_category: str = "default",
) -> float:
    """Calculate effective spread after accounting for fees.

    Args:
        bid_price: Bid price
        ask_price: Ask price
        contracts: Number of contracts
        market_category: Market category

    Returns:
        Effective spread as probability (0.0-1.0)
    """
    spread = (int(ask_price) - int(bid_price)) / 100.0

    # Subtract fees from both sides
    bid_fee = fee_buffer_probability(bid_price, market_category)
    ask_fee = fee_buffer_probability(ask_price, market_category)

    effective_spread = spread - bid_fee - ask_fee

    return max(0.0, effective_spread)

