"""Kalshi HTTP client for market discovery."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

import httpx

from src.clients.kalshi_auth import KalshiAuth
from src.models.types import KalshiMarket

logger = logging.getLogger(__name__)


class KalshiHttpClient:
    """HTTP client for Kalshi API."""
    
    DEMO_BASE_URL = "https://demo-api.kalshi.co/trade-api/v2"
    PROD_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"  # Updated URL
    
    def __init__(
        self, 
        auth: KalshiAuth | None = None,
        is_demo: bool = True,
        timeout: float = 10.0
    ):
        """Initialize client.
        
        Args:
            auth: Authentication handler (None for public endpoints)
            is_demo: Whether to use demo environment
            timeout: Request timeout in seconds
        """
        self.auth = auth
        base_url = self.DEMO_BASE_URL if is_demo else self.PROD_BASE_URL
        
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
        
        logger.info(f"KalshiHttpClient initialized for {'demo' if is_demo else 'prod'}")
    
    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
    
    async def get_markets(
        self,
        category: str | None = None,
        status: str | None = None,
        limit: int = 1000,
        cursor: str | None = None
    ) -> list[KalshiMarket]:
        """Get markets from Kalshi.
        
        Args:
            category: Filter by category (optional)
            status: Filter by status (optional) 
            limit: Maximum number of markets to return
            cursor: Pagination cursor
            
        Returns:
            List of Kalshi markets
        """
        markets = []
        
        try:
            params: dict[str, Any] = {"limit": limit}
            
            if category:
                params["category"] = category
            if status:
                params["status"] = status
            if cursor:
                params["cursor"] = cursor
            
            # Build headers
            headers = {}
            if self.auth:
                headers.update(self.auth.sign_request("GET", "/markets"))
            
            response = await self._client.get("/markets", params=params, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"Kalshi API error: {response.status_code} {response.text}")
                return markets
                
            data = response.json()
            
            if "markets" not in data:
                logger.warning("No markets field in Kalshi response")
                return markets
            
            for market_data in data["markets"]:
                try:
                    market = self._parse_market(market_data)
                    if market:
                        markets.append(market)
                except Exception as e:
                    logger.debug(f"Error parsing market {market_data.get('ticker', 'unknown')}: {e}")
            
            logger.info(f"Retrieved {len(markets)} markets from Kalshi")
            
            # Handle pagination if there's a cursor
            if "cursor" in data and len(markets) < 2000:  # Safety limit (reduced)
                # Rate limiting to avoid 429 errors
                await asyncio.sleep(0.5)
                
                next_markets = await self.get_markets(
                    category=category,
                    status=status,
                    limit=limit,
                    cursor=data["cursor"]
                )
                markets.extend(next_markets)
            
            return markets
            
        except Exception as e:
            logger.error(f"Error fetching Kalshi markets: {e}", exc_info=True)
            return markets
    
    async def get_live_soccer_markets(self) -> list[KalshiMarket]:
        """Get live soccer markets efficiently from production API."""
        logger.info("Fetching live soccer markets from Kalshi production...")
        
        # Get only SPORTS category with open status (most efficient)
        try:
            sports_markets = await self.get_markets(category="SPORTS", status="open", limit=500)
            
            # Filter for soccer/football related markets
            soccer_markets = [
                market for market in sports_markets
                if self._is_soccer_market(market)
            ]
            
            logger.info(f"Found {len(soccer_markets)} live soccer markets out of {len(sports_markets)} sports markets")
            
            if not soccer_markets:
                # Try alternative approach - search for soccer-specific patterns
                logger.info("No soccer markets found in SPORTS category, trying broader search...")
                
                # Get markets without category filter but with smaller limit
                all_markets = await self.get_markets(status="open", limit=200)
                soccer_markets = [
                    market for market in all_markets
                    if self._is_soccer_market(market)
                ]
                logger.info(f"Found {len(soccer_markets)} soccer markets in broader search")
            
            return soccer_markets
            
        except Exception as e:
            logger.error(f"Error fetching live soccer markets: {e}")
            return []
    
    async def get_soccer_markets(self) -> list[KalshiMarket]:
        """Get all soccer-related markets (fallback method)."""
        return await self.get_live_soccer_markets()
    
    def _is_soccer_market(self, market: KalshiMarket) -> bool:
        """Check if a market is soccer/football related."""
        text = f"{market.title} {market.subtitle or ''} {market.category}".lower()
        
        # Soccer/football keywords
        soccer_keywords = [
            "soccer", "football", "fifa", "uefa", "premier league", "epl",
            "bundesliga", "la liga", "serie a", "ligue 1", "champions league",
            "world cup", "euro", "match", "goal", "arsenal", "chelsea", "liverpool",
            "manchester", "barcelona", "real madrid", "bayern", "psg", "juventus"
        ]
        
        return any(keyword in text for keyword in soccer_keywords)
    
    def _parse_market(self, data: dict[str, Any]) -> KalshiMarket | None:
        """Parse market data from Kalshi API response."""
        try:
            ticker = data.get("ticker")
            if not ticker:
                return None
            
            # Parse times
            open_time = None
            close_time = None
            settle_time = None
            
            if data.get("open_time"):
                try:
                    open_time = datetime.fromisoformat(data["open_time"].replace("Z", "+00:00"))
                except Exception:
                    pass
            
            if data.get("close_time"):
                try:
                    close_time = datetime.fromisoformat(data["close_time"].replace("Z", "+00:00"))
                except Exception:
                    pass
                    
            if data.get("settle_time"):
                try:
                    settle_time = datetime.fromisoformat(data["settle_time"].replace("Z", "+00:00"))
                except Exception:
                    pass
            
            return KalshiMarket(
                ticker=ticker,
                title=data.get("title", ""),
                subtitle=data.get("subtitle"),
                category=data.get("category", ""),
                status=data.get("status", ""),
                yes_ask=data.get("yes_ask"),
                yes_bid=data.get("yes_bid"),
                no_ask=data.get("no_ask"),
                no_bid=data.get("no_bid"),
                open_time=open_time,
                close_time=close_time,
                settle_time=settle_time,
                raw_data=data
            )
            
        except Exception as e:
            logger.debug(f"Error parsing market data: {e}")
            return None