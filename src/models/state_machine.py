"""State machine for per-market trading states."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

from kalshi_trader.util.time import current_epoch_ms

logger = logging.getLogger(__name__)


class MarketState(str, Enum):
    """Market trading state."""

    INIT = "INIT"
    WAIT_DATA = "WAIT_DATA"
    QUOTING = "QUOTING"
    PAUSED = "PAUSED"
    FLATTENING = "FLATTENING"
    DONE = "DONE"


@dataclass
class MarketStateMachine:
    """State machine for a single market."""

    market_id: str
    state: MarketState = MarketState.INIT
    state_entered_ts_ms: int = field(default_factory=current_epoch_ms)
    pause_until_ts_ms: int | None = None
    warmup_start_ts_ms: int | None = None

    def transition_to(self, new_state: MarketState) -> None:
        """Transition to a new state."""
        if self.state == new_state:
            return

        logger.info(
            "Market %s: %s -> %s",
            self.market_id,
            self.state.value,
            new_state.value,
        )
        self.state = new_state
        self.state_entered_ts_ms = current_epoch_ms()

    def set_pause_until(self, pause_seconds: int) -> None:
        """Set pause until timestamp."""
        self.pause_until_ts_ms = current_epoch_ms() + (pause_seconds * 1000)
        self.transition_to(MarketState.PAUSED)

    def can_exit_pause(self) -> bool:
        """Check if can exit pause state."""
        if self.state != MarketState.PAUSED:
            return False

        if self.pause_until_ts_ms is None:
            return True

        return current_epoch_ms() >= self.pause_until_ts_ms

    def start_warmup(self) -> None:
        """Start warmup period."""
        if self.warmup_start_ts_ms is None:
            self.warmup_start_ts_ms = current_epoch_ms()

    def is_warmup_complete(self, warmup_seconds: int) -> bool:
        """Check if warmup is complete."""
        if self.warmup_start_ts_ms is None:
            return False

        elapsed = (current_epoch_ms() - self.warmup_start_ts_ms) / 1000.0
        return elapsed >= warmup_seconds

