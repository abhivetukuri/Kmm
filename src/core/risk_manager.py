"""Risk manager for position limits and circuit breakers."""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import DefaultDict

from kalshi_trader.types import Cents, PriceTicks, Quantity

logger = logging.getLogger(__name__)


@dataclass
class PositionState:
    """Position state for a market."""

    net_contracts: int  # Positive = long, negative = short
    avg_entry_price: PriceTicks
    realized_pnl_cents: Cents
    unrealized_pnl_cents: Cents


@dataclass
class RiskState:
    """Current risk state."""

    positions: dict[str, PositionState] = field(default_factory=dict)
    total_notional: float = 0.0
    drawdown_cents: Cents = Cents(0)
    fill_notional_by_market: DefaultDict[str, list[tuple[int, float]]] = field(
        default_factory=lambda: defaultdict(list)
    )  # (timestamp_ms, notional)
    paused_markets: set[str] = field(default_factory=set)


class RiskManager:
    """Manages risk limits and circuit breakers."""

    def __init__(
        self,
        max_position_notional_demo: float = 25.00,
        max_position_notional_live: float = 10.00,
        max_total_notional_demo: float = 125.00,
        max_total_notional_live: float = 50.00,
        max_filled_notional_per_minute_demo: float = 20.00,
        max_filled_notional_per_minute_live: float = 8.00,
        drawdown_limit_demo: float = 50.00,
        drawdown_limit_live: float = 20.00,
        is_demo: bool = True,
    ):
        """Initialize risk manager.

        Args:
            max_position_notional_demo: Max position notional per market in demo ($)
            max_position_notional_live: Max position notional per market in live ($)
            max_total_notional_demo: Max total notional across all markets in demo ($)
            max_total_notional_live: Max total notional across all markets in live ($)
            max_filled_notional_per_minute_demo: Max filled notional per minute in demo ($)
            max_filled_notional_per_minute_live: Max filled notional per minute in live ($)
            drawdown_limit_demo: Drawdown limit in demo ($)
            drawdown_limit_live: Drawdown limit in live ($)
            is_demo: Whether running in demo mode
        """
        self._max_position_notional = (
            max_position_notional_demo if is_demo else max_position_notional_live
        )
        self._max_total_notional = max_total_notional_demo if is_demo else max_total_notional_live
        self._max_filled_notional_per_minute = (
            max_filled_notional_per_minute_demo if is_demo else max_filled_notional_per_minute_live
        )
        self._drawdown_limit = drawdown_limit_demo if is_demo else drawdown_limit_live
        self._is_demo = is_demo

        self._state = RiskState()

    def check_position_limit(
        self,
        market_id: str,
        current_mid_price: float,
        net_contracts: int,
    ) -> tuple[bool, str]:
        """Check if position is within limits.

        Args:
            market_id: Market ID
            current_mid_price: Current mid price (0.01-0.99)
            net_contracts: Net position (positive = long, negative = short)

        Returns:
            (is_ok, reason)
        """
        pos_notional = abs(net_contracts) * current_mid_price

        if pos_notional >= self._max_position_notional:
            return False, f"position_limit_exceeded: {pos_notional:.2f} >= {self._max_position_notional:.2f}"

        return True, "ok"

    def check_total_notional(self, total_notional: float) -> tuple[bool, str]:
        """Check if total notional is within limits.

        Args:
            total_notional: Total notional across all markets ($)

        Returns:
            (is_ok, reason)
        """
        if total_notional >= self._max_total_notional:
            return False, f"total_notional_limit_exceeded: {total_notional:.2f} >= {self._max_total_notional:.2f}"

        return True, "ok"

    def check_fill_rate(self, market_id: str, fill_notional: float) -> tuple[bool, str]:
        """Check if fill rate is within limits.

        Args:
            market_id: Market ID
            fill_notional: Fill notional in this fill ($)

        Returns:
            (is_ok, reason, pause_seconds)
        """
        from kalshi_trader.util.time import current_epoch_ms

        now_ms = current_epoch_ms()
        one_minute_ago_ms = now_ms - 60_000

        # Clean old entries
        self._state.fill_notional_by_market[market_id] = [
            (ts, notional)
            for ts, notional in self._state.fill_notional_by_market[market_id]
            if ts > one_minute_ago_ms
        ]

        # Add new fill
        self._state.fill_notional_by_market[market_id].append((now_ms, fill_notional))

        # Calculate total in last minute
        total_minute = sum(notional for _, notional in self._state.fill_notional_by_market[market_id])

        if total_minute >= self._max_filled_notional_per_minute:
            pause_seconds = 120
            return False, f"fill_rate_limit_exceeded: {total_minute:.2f} >= {self._max_filled_notional_per_minute:.2f}", pause_seconds

        return True, "ok", 0

    def check_drawdown(
        self,
        realized_pnl_cents: Cents,
        unrealized_pnl_cents: Cents,
    ) -> tuple[bool, str]:
        """Check if drawdown is within limits.

        Args:
            realized_pnl_cents: Realized PnL in cents
            unrealized_pnl_cents: Unrealized PnL in cents

        Returns:
            (is_ok, reason)
        """
        total_pnl_cents = int(realized_pnl_cents) + int(unrealized_pnl_cents)
        drawdown_cents = abs(min(0, total_pnl_cents))
        drawdown_limit_cents = int(self._drawdown_limit * 100)

        if drawdown_cents >= drawdown_limit_cents:
            return False, f"drawdown_limit_exceeded: {drawdown_cents/100:.2f} >= {self._drawdown_limit:.2f}"

        return True, "ok"

    def update_position(
        self,
        market_id: str,
        net_contracts: int,
        avg_entry_price: PriceTicks,
        realized_pnl_cents: Cents,
        unrealized_pnl_cents: Cents,
    ) -> None:
        """Update position state.

        Args:
            market_id: Market ID
            net_contracts: Net position
            avg_entry_price: Average entry price
            realized_pnl_cents: Realized PnL
            unrealized_pnl_cents: Unrealized PnL
        """
        self._state.positions[market_id] = PositionState(
            net_contracts=net_contracts,
            avg_entry_price=avg_entry_price,
            realized_pnl_cents=realized_pnl_cents,
            unrealized_pnl_cents=unrealized_pnl_cents,
        )

    def get_position(self, market_id: str) -> PositionState | None:
        """Get position state for a market."""
        return self._state.positions.get(market_id)

    def pause_market(self, market_id: str) -> None:
        """Pause trading for a market."""
        self._state.paused_markets.add(market_id)
        logger.warning("Paused market %s due to risk limit", market_id)

    def unpause_market(self, market_id: str) -> None:
        """Resume trading for a market."""
        self._state.paused_markets.discard(market_id)
        logger.info("Unpaused market %s", market_id)

    def is_paused(self, market_id: str) -> bool:
        """Check if market is paused."""
        return market_id in self._state.paused_markets

