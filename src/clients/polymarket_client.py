"""Polymarket HTTP client for market data polling."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class PolymarketTokenData:
    """Best bid/ask data for a Polymarket token."""

    token_id: str
    best_bid: float | None  # Probability 0.0-1.0
    best_ask: float | None
    best_bid_size: float | None
    best_ask_size: float | None
    last_price: float | None
    timestamp_ms: int


@dataclass
class PolymarketMarketData:
    """Market data for a Polymarket market."""

    market_slug: str
    tokens: dict[str, PolymarketTokenData]  # token_id -> data
    timestamp_ms: int


class PolymarketClient:
    """HTTP client for Polymarket REST API.

    Phase 1: REST polling only.
    Phase 2: Add WebSocket support later.
    """

    BASE_URL = "https://clob.polymarket.com"

    def __init__(self, timeout: float = 5.0):
        """Initialize the client."""
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=timeout,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
        logger.info("PolymarketClient initialized")

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def get_market_data(self, market_slug: str, token_ids: list[str]) -> PolymarketMarketData | None:
        """Get best bid/ask for specified tokens in a market.

        Args:
            market_slug: Polymarket market slug
            token_ids: List of token IDs to fetch

        Returns:
            Market data or None if error
        """
        try:
            # Polymarket CLOB API endpoint for market data
            # Using the public market endpoint
            url = f"/markets/{market_slug}"
            resp = await self._client.get(url)

            if resp.status_code != 200:
                logger.warning("Polymarket API error: %d %s", resp.status_code, resp.text)
                return None

            data = resp.json()

            # Parse market data
            # Note: Actual Polymarket API structure may differ
            # This is a placeholder that needs to be adjusted based on real API docs
            tokens: dict[str, PolymarketTokenData] = {}

            # Extract token data from response
            # Assuming response has structure like:
            # {
            #   "tokens": [
            #     {
            #       "token_id": "...",
            #       "best_bid": 0.45,
            #       "best_ask": 0.47,
            #       ...
            #     }
            #   ]
            # }
            if "tokens" in data:
                for token_data in data["tokens"]:
                    token_id = token_data.get("token_id")
                    if token_id in token_ids:
                        tokens[token_id] = PolymarketTokenData(
                            token_id=token_id,
                            best_bid=token_data.get("best_bid"),
                            best_ask=token_data.get("best_ask"),
                            best_bid_size=token_data.get("best_bid_size"),
                            best_ask_size=token_data.get("best_ask_size"),
                            last_price=token_data.get("last_price"),
                            timestamp_ms=token_data.get("timestamp_ms", 0),
                        )

            # If we didn't get data from the market endpoint, try token-specific endpoint
            if not tokens:
                for token_id in token_ids:
                    token_data = await self._get_token_data(token_id)
                    if token_data:
                        tokens[token_id] = token_data

            if not tokens:
                logger.warning("No token data found for market %s", market_slug)
                return None

            from kalshi_trader.util.time import current_epoch_ms

            return PolymarketMarketData(
                market_slug=market_slug,
                tokens=tokens,
                timestamp_ms=current_epoch_ms(),
            )

        except Exception as e:
            logger.error("Error fetching Polymarket data: %s", e, exc_info=True)
            return None

    async def _get_token_data(self, token_id: str) -> PolymarketTokenData | None:
        """Get data for a specific token.

        Args:
            token_id: Token ID

        Returns:
            Token data or None
        """
        try:
            # Polymarket token-specific endpoint
            url = f"/tokens/{token_id}/book"
            resp = await self._client.get(url)

            if resp.status_code != 200:
                return None

            data = resp.json()

            # Parse orderbook data
            # Assuming structure like:
            # {
            #   "bids": [[price, size], ...],
            #   "asks": [[price, size], ...],
            #   "last_price": 0.45
            # }
            best_bid = None
            best_ask = None
            best_bid_size = None
            best_ask_size = None

            if "bids" in data and data["bids"]:
                best_bid = float(data["bids"][0][0])
                best_bid_size = float(data["bids"][0][1])

            if "asks" in data and data["asks"]:
                best_ask = float(data["asks"][0][0])
                best_ask_size = float(data["asks"][0][1])

            from kalshi_trader.util.time import current_epoch_ms

            return PolymarketTokenData(
                token_id=token_id,
                best_bid=best_bid,
                best_ask=best_ask,
                best_bid_size=best_bid_size,
                best_ask_size=best_ask_size,
                last_price=data.get("last_price"),
                timestamp_ms=current_epoch_ms(),
            )

        except Exception as e:
            logger.debug("Error fetching token %s: %s", token_id, e)
            return None

