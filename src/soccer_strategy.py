"""Soccer market making strategy integrating Polymarket and Kalshi."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from kalshi_trader.engine.engine import Engine
from kalshi_trader.soccer.config import SoccerConfig, SoccerMarketConfig
from kalshi_trader.soccer.fair_price import FairPriceCalculator, FairPriceInputs, FairPriceOutput
from kalshi_trader.soccer.market_data_store import MarketDataStore
from kalshi_trader.soccer.match_phase import MatchPhase, get_match_phase
from kalshi_trader.soccer.polymarket_client import PolymarketClient
from kalshi_trader.soccer.quoting import QuotingEngine, QuotingOutput
from kalshi_trader.soccer.risk_manager import RiskManager
from kalshi_trader.soccer.state_machine import MarketState, MarketStateMachine
from kalshi_trader.strategy.base import DesiredQuotes, OrderbookView, Quote, Strategy
from kalshi_trader.types import MarketTicker, PriceTicks, Quantity, TopOfBook

logger = logging.getLogger(__name__)


@dataclass
class MarketContext:
    """Context for a single market."""

    config: SoccerMarketConfig
    state_machine: MarketStateMachine
    last_poly_update_ms: int = 0
    last_quote_update_ms: int = 0


class SoccerMarketMakerStrategy(Strategy):
    """Soccer market making strategy using Polymarket fair value.

    This strategy:
    1. Polls Polymarket for fair value signals
    2. Combines with Kalshi orderbook data
    3. Calculates fair price using dynamic weights
    4. Quotes bid/ask around fair with appropriate spreads
    5. Manages risk limits and position controls
    6. Handles match phases (pre-match, in-play, stop-quoting)
    """

    def __init__(
        self,
        config: SoccerConfig,
        engine: Engine,
        poly_client: PolymarketClient,
    ):
        """Initialize strategy.

        Args:
            config: Soccer configuration
            engine: Trading engine
            poly_client: Polymarket client
        """
        self._config = config
        self._engine = engine
        self._poly_client = poly_client
        self._is_demo = config.env == "demo"

        # Components
        self._data_store = MarketDataStore(
            stale_seconds_prematch=config.params.stale_seconds_prematch,
            stale_seconds_inplay=config.params.stale_seconds_inplay,
        )
        self._fair_calculator = FairPriceCalculator(
            w_poly_base_prematch=config.params.w_poly_base_prematch,
            w_poly_base_inplay=config.params.w_poly_base_inplay,
            poly_spread_narrow_threshold=config.params.poly_spread_narrow_threshold,
            poly_spread_wide_threshold=config.params.poly_spread_wide_threshold,
            poly_spread_narrow_bonus=config.params.poly_spread_narrow_bonus,
            poly_spread_wide_penalty=config.params.poly_spread_wide_penalty,
            shock_score_threshold=config.params.shock_score_threshold,
        )
        self._quoting_engine = QuotingEngine(
            base_half_spread_prematch=config.params.base_half_spread_prematch,
            base_half_spread_inplay=config.params.base_half_spread_inplay,
            adv_buffer_prematch=config.params.adv_buffer_prematch,
            adv_buffer_inplay=config.params.adv_buffer_inplay,
            adv_buffer_shock=config.params.adv_buffer_shock,
            max_order_notional_demo=config.params.max_order_notional_demo,
            max_order_notional_live=config.params.max_order_notional_live,
            max_contracts_per_order_demo=config.params.max_contracts_per_order_demo,
            max_contracts_per_order_live=config.params.max_contracts_per_order_live,
            max_size_vs_depth_ratio=config.params.max_size_vs_depth_ratio,
            is_demo=self._is_demo,
        )
        self._risk_manager = RiskManager(
            max_position_notional_demo=config.params.max_position_notional_demo,
            max_position_notional_live=config.params.max_position_notional_live,
            max_total_notional_demo=config.params.max_total_notional_demo,
            max_total_notional_live=config.params.max_total_notional_live,
            max_filled_notional_per_minute_demo=config.params.max_filled_notional_per_minute_demo,
            max_filled_notional_per_minute_live=config.params.max_filled_notional_per_minute_live,
            drawdown_limit_demo=config.params.drawdown_limit_demo,
            drawdown_limit_live=config.params.drawdown_limit_live,
            is_demo=self._is_demo,
        )

        # Market contexts
        self._contexts: dict[str, MarketContext] = {}
        for market_config in config.markets:
            self._contexts[market_config.id] = MarketContext(
                config=market_config,
                state_machine=MarketStateMachine(market_id=market_config.id),
            )

        # Background polling task
        self._polling_task: asyncio.Task | None = None
        self._running = False

    @property
    def name(self) -> str:
        """Strategy name."""
        return "soccer_market_maker"

    async def start(self) -> None:
        """Start background polling tasks."""
        self._running = True
        self._polling_task = asyncio.create_task(self._poll_polymarket_loop())

    async def stop(self) -> None:
        """Stop background tasks."""
        self._running = False
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass

    def on_market_event(
        self,
        market_ticker: MarketTicker,
        ob: OrderbookView,
    ) -> DesiredQuotes:
        """Handle market event from Kalshi.

        This is called by the engine when Kalshi orderbook updates.
        We update our data store and potentially trigger quote updates.

        Args:
            market_ticker: Market ticker
            ob: Orderbook view

        Returns:
            Desired quotes (handled asynchronously via engine slots)
        """
        # Find market config
        market_context = self._find_context_by_ticker(market_ticker)
        if market_context is None:
            return DesiredQuotes.empty()

        # Get top of book
        tob = ob.top_of_book(market_ticker)
        if tob is None:
            return DesiredQuotes.empty()

        # Update data store
        match_phase = get_match_phase(
            market_context.config.start_time_utc,
            market_context.config.scheduled_end_time_utc,
            self._config.params.stop_before_end_seconds,
        )

        snapshot = self._data_store.update_kalshi(
            market_context.config.id,
            market_ticker,
            tob,
            match_phase.value,
        )

        # Update state machine
        self._update_state_machine(market_context, snapshot, match_phase)

        # If we're in QUOTING state, calculate and return quotes
        if market_context.state_machine.state == MarketState.QUOTING:
            return self._calculate_quotes(market_context, snapshot, match_phase, tob)
        else:
            return DesiredQuotes.empty()

    def _find_context_by_ticker(self, ticker: MarketTicker) -> MarketContext | None:
        """Find market context by Kalshi ticker."""
        for context in self._contexts.values():
            if context.config.kalshi_ticker == ticker:
                return context
        return None

    def _update_state_machine(
        self,
        context: MarketContext,
        snapshot,
        match_phase: MatchPhase,
    ) -> None:
        """Update state machine based on current conditions."""
        sm = context.state_machine

        # Handle STOP_QUOTING phase
        if match_phase == MatchPhase.STOP_QUOTING:
            if sm.state != MarketState.DONE:
                sm.transition_to(MarketState.DONE)
            return

        # State transitions
        if sm.state == MarketState.INIT:
            sm.transition_to(MarketState.WAIT_DATA)
            sm.start_warmup()

        elif sm.state == MarketState.WAIT_DATA:
            # Check if we have fresh data from both venues
            has_kalshi = not snapshot.kalshi_stale and snapshot.kalshi_mid is not None
            has_poly = not snapshot.polymarket_stale and snapshot.polymarket_mid is not None

            if has_kalshi and has_poly:
                if sm.is_warmup_complete(self._config.params.warmup_seconds):
                    if not self._risk_manager.is_paused(context.config.id):
                        sm.transition_to(MarketState.QUOTING)
            else:
                # Reset warmup if data is stale
                sm.warmup_start_ts_ms = None

        elif sm.state == MarketState.QUOTING:
            # Check for pause conditions
            if snapshot.kalshi_stale and snapshot.polymarket_stale:
                sm.transition_to(MarketState.PAUSED)
            elif self._risk_manager.is_paused(context.config.id):
                sm.transition_to(MarketState.PAUSED)

        elif sm.state == MarketState.PAUSED:
            # Check if we can resume
            if sm.can_exit_pause():
                has_kalshi = not snapshot.kalshi_stale and snapshot.kalshi_mid is not None
                has_poly = not snapshot.polymarket_stale and snapshot.polymarket_mid is not None

                if has_kalshi and has_poly and match_phase != MatchPhase.STOP_QUOTING:
                    if not self._risk_manager.is_paused(context.config.id):
                        sm.transition_to(MarketState.QUOTING)

    def _calculate_quotes(
        self,
        context: MarketContext,
        snapshot,
        match_phase: MatchPhase,
        tob: TopOfBook,
    ) -> DesiredQuotes:
        """Calculate desired quotes."""
        # Get fair price inputs
        poly_mid = snapshot.polymarket_mid
        poly_spread = snapshot.polymarket_spread
        poly_stale = snapshot.polymarket_stale
        poly_depth_strong = (
            snapshot.polymarket_top_depth_bid is not None
            and snapshot.polymarket_top_depth_ask is not None
            and snapshot.polymarket_top_depth_bid > 100
            and snapshot.polymarket_top_depth_ask > 100
        )

        kalshi_mid = snapshot.kalshi_mid
        kalshi_spread = None
        if snapshot.kalshi_best_bid_price and snapshot.kalshi_best_ask_price:
            kalshi_spread = snapshot.kalshi_best_ask_price - snapshot.kalshi_best_bid_price

        fair_inputs = FairPriceInputs(
            poly_mid=poly_mid,
            poly_spread=poly_spread,
            poly_stale=poly_stale,
            poly_depth_strong=poly_depth_strong,
            kalshi_mid=kalshi_mid,
            kalshi_spread=kalshi_spread,
            kalshi_stale=snapshot.kalshi_stale,
            match_phase=match_phase.value,
        )

        # Calculate fair price
        fair_output = self._fair_calculator.calculate(fair_inputs)

        # Handle shock
        if fair_output.is_shocked:
            context.state_machine.set_pause_until(self._config.params.pause_seconds_shock)
            return DesiredQuotes.empty()

        # Get current prices from snapshot (for post-only checks)
        # The engine will handle comparing desired vs live orders
        current_bid_price = (
            PriceTicks(int(snapshot.kalshi_best_bid_price * 100))
            if snapshot.kalshi_best_bid_price
            else None
        )
        current_ask_price = (
            PriceTicks(int(snapshot.kalshi_best_ask_price * 100))
            if snapshot.kalshi_best_ask_price
            else None
        )

        # Calculate quotes
        quoting_output = self._quoting_engine.calculate_quotes(
            fair_output,
            snapshot,
            match_phase.value,
            current_bid_price,
            current_ask_price,
        )

        if quoting_output.reason != "ok":
            logger.debug("Market %s: No quotes - %s", context.config.id, quoting_output.reason)
            return DesiredQuotes.empty()

        # Convert to DesiredQuotes
        yes_quote = None
        no_quote = None

        if quoting_output.bid:
            yes_quote = Quote(price=quoting_output.bid.price, qty=quoting_output.bid.qty)

        if quoting_output.ask:
            no_quote = Quote(price=quoting_output.ask.price, qty=quoting_output.ask.qty)

        return DesiredQuotes(yes=yes_quote, no=no_quote)

    async def _poll_polymarket_loop(self) -> None:
        """Background loop to poll Polymarket data."""
        while self._running:
            try:
                await self._poll_all_markets()
                # Sleep based on match phase (will be optimized per market later)
                await asyncio.sleep(2.0)  # Default 2 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in Polymarket polling loop: %s", e, exc_info=True)
                await asyncio.sleep(5.0)

    async def _poll_all_markets(self) -> None:
        """Poll Polymarket data for all markets."""
        for context in self._contexts.values():
            try:
                await self._poll_market(context)
            except Exception as e:
                logger.error("Error polling market %s: %s", context.config.id, e, exc_info=True)

    async def _poll_market(self, context: MarketContext) -> None:
        """Poll Polymarket data for a single market."""
        # Determine polling interval based on match phase
        match_phase = get_match_phase(
            context.config.start_time_utc,
            context.config.scheduled_end_time_utc,
            self._config.params.stop_before_end_seconds,
        )

        if match_phase == MatchPhase.STOP_QUOTING:
            return  # Don't poll if we're stopping

        # Get token ID (for two-outcome, use the YES token)
        token_id = context.config.polymarket.token_ids.get("home") or context.config.polymarket.token_ids.get("yes")
        if not token_id:
            return

        # Poll Polymarket
        poly_data = await self._poly_client.get_market_data(
            context.config.polymarket.market_slug,
            [token_id],
        )

        if poly_data:
            # Update data store
            snapshot = self._data_store.update_polymarket(
                context.config.id,
                poly_data,
                token_id,
                match_phase.value,
            )

            context.last_poly_update_ms = poly_data.timestamp_ms

            # Trigger quote recalculation by publishing a market event
            # (The engine will call on_market_event)
            # For now, we rely on Kalshi updates to trigger quotes
            # In a full implementation, we'd trigger here too

