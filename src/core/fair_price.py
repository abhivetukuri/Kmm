"""Fair price calculator using Polymarket and Kalshi signals."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from kalshi_trader.soccer.polymarket_client import PolymarketTokenData
from kalshi_trader.types import PriceTicks, TopOfBook
from kalshi_trader.util.time import current_epoch_ms

logger = logging.getLogger(__name__)


@dataclass
class FairPriceInputs:
    """Inputs for fair price calculation."""

    poly_mid: float | None  # Polymarket mid price (0.0-1.0)
    poly_spread: float | None  # Polymarket spread
    poly_stale: bool  # Is Polymarket data stale?
    poly_depth_strong: bool  # Is Polymarket depth strong?
    kalshi_mid: float | None  # Kalshi mid price (0.01-0.99)
    kalshi_spread: float | None  # Kalshi spread
    kalshi_stale: bool  # Is Kalshi data stale?
    match_phase: str  # "PREMATCH" or "INPLAY"
    timestamp_ms: int = field(default_factory=lambda: current_epoch_ms())


@dataclass
class FairPriceOutput:
    """Output of fair price calculation."""

    fair: float  # Fair price as probability (0.01-0.99)
    w_poly: float  # Weight on Polymarket (0.0-1.0)
    shock_score: float  # Shock detection score
    is_shocked: bool  # Whether shock detected
    timestamp_ms: int


class FairPriceCalculator:
    """Calculates fair price from Polymarket and Kalshi signals."""

    def __init__(
        self,
        w_poly_base_prematch: float = 0.70,
        w_poly_base_inplay: float = 0.85,
        poly_spread_narrow_threshold: float = 0.02,
        poly_spread_wide_threshold: float = 0.06,
        poly_spread_narrow_bonus: float = 0.05,
        poly_spread_wide_penalty: float = 0.10,
        shock_score_threshold: float = 3.0,
    ):
        """Initialize calculator.

        Args:
            w_poly_base_prematch: Base Polymarket weight pre-match
            w_poly_base_inplay: Base Polymarket weight in-play
            poly_spread_narrow_threshold: Spread threshold for narrow (add bonus)
            poly_spread_wide_threshold: Spread threshold for wide (subtract penalty)
            poly_spread_narrow_bonus: Bonus to add when spread is narrow
            poly_spread_wide_penalty: Penalty when spread is wide
            shock_score_threshold: Shock detection threshold
        """
        self._w_poly_base_prematch = w_poly_base_prematch
        self._w_poly_base_inplay = w_poly_base_inplay
        self._poly_spread_narrow_threshold = poly_spread_narrow_threshold
        self._poly_spread_wide_threshold = poly_spread_wide_threshold
        self._poly_spread_narrow_bonus = poly_spread_narrow_bonus
        self._poly_spread_wide_penalty = poly_spread_wide_penalty
        self._shock_score_threshold = shock_score_threshold

        # EWMA for shock detection
        self._poly_mid_ewma: float | None = None
        self._poly_vol_ewma: float | None = None
        self._alpha = 0.1  # EWMA decay factor

    def calculate(self, inputs: FairPriceInputs) -> FairPriceOutput:
        """Calculate fair price.

        Args:
            inputs: Input data

        Returns:
            Fair price output
        """
        # Calculate Polymarket weight
        w_poly = self._calculate_weight(inputs)

        # Calculate fair price
        fair = self._calculate_fair(inputs, w_poly)

        # Shock detection
        shock_score, is_shocked = self._detect_shock(inputs)

        return FairPriceOutput(
            fair=fair,
            w_poly=w_poly,
            shock_score=shock_score,
            is_shocked=is_shocked,
            timestamp_ms=inputs.timestamp_ms,
        )

    def _calculate_weight(self, inputs: FairPriceInputs) -> float:
        """Calculate dynamic Polymarket weight."""
        # Base weight
        if inputs.match_phase == "INPLAY":
            w_poly = self._w_poly_base_inplay
        else:
            w_poly = self._w_poly_base_prematch

        # Adjustments
        if inputs.poly_stale:
            # If Polymarket is stale, don't use it
            return 0.0

        if inputs.poly_spread is not None:
            if inputs.poly_spread <= self._poly_spread_narrow_threshold and inputs.poly_depth_strong:
                w_poly += self._poly_spread_narrow_bonus
            elif inputs.poly_spread >= self._poly_spread_wide_threshold:
                w_poly -= self._poly_spread_wide_penalty

        # Clamp to [0.0, 0.95]
        w_poly = max(0.0, min(0.95, w_poly))

        return w_poly

    def _calculate_fair(self, inputs: FairPriceInputs, w_poly: float) -> float:
        """Calculate fair price from weighted average."""
        # If no Polymarket data, use Kalshi only
        if inputs.poly_mid is None or w_poly == 0.0:
            if inputs.kalshi_mid is None:
                logger.warning("No market data available for fair price")
                return 0.50  # Default to 50%
            return inputs.kalshi_mid

        # If no Kalshi data, use Polymarket only
        if inputs.kalshi_mid is None:
            return inputs.poly_mid

        # Weighted average
        fair = w_poly * inputs.poly_mid + (1 - w_poly) * inputs.kalshi_mid

        # Clamp to valid range [0.01, 0.99]
        fair = max(0.01, min(0.99, fair))

        return fair

    def _detect_shock(self, inputs: FairPriceInputs) -> tuple[float, bool]:
        """Detect price shocks using EWMA.

        Returns:
            (shock_score, is_shocked)
        """
        if inputs.poly_mid is None:
            return 0.0, False

        poly_mid = inputs.poly_mid

        # Initialize EWMA
        if self._poly_mid_ewma is None:
            self._poly_mid_ewma = poly_mid
            self._poly_vol_ewma = 0.01  # Initial volatility estimate
            return 0.0, False

        # Update EWMA
        change = abs(poly_mid - self._poly_mid_ewma)
        self._poly_mid_ewma = self._alpha * poly_mid + (1 - self._alpha) * self._poly_mid_ewma
        self._poly_vol_ewma = self._alpha * change + (1 - self._alpha) * self._poly_vol_ewma

        # Calculate shock score
        vol = max(0.01, self._poly_vol_ewma)
        shock_score = change / vol

        is_shocked = shock_score >= self._shock_score_threshold

        if is_shocked:
            logger.warning(
                "Shock detected: score=%.2f, poly_mid=%.4f, ewma=%.4f",
                shock_score,
                poly_mid,
                self._poly_mid_ewma,
            )

        return shock_score, is_shocked

    def reset_ewma(self) -> None:
        """Reset EWMA state (e.g., on market reset)."""
        self._poly_mid_ewma = None
        self._poly_vol_ewma = None

