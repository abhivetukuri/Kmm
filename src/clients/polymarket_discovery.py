"""Polymarket HTTP client for market discovery and data polling."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

import httpx

from src.models.types import PolymarketMarket, PolymarketToken

logger = logging.getLogger(__name__)


class PolymarketDiscoveryClient:
    """HTTP client for Polymarket market discovery."""
    
    GAMMA_BASE_URL = "https://gamma-api.polymarket.com"
    CLOB_BASE_URL = "https://clob.polymarket.com"
    
    def __init__(self, timeout: float = 10.0):
        """Initialize the client."""
        self._gamma_client = httpx.AsyncClient(
            base_url=self.GAMMA_BASE_URL,
            timeout=timeout,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
        
        self._clob_client = httpx.AsyncClient(
            base_url=self.CLOB_BASE_URL,
            timeout=timeout,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
        
        logger.info("PolymarketDiscoveryClient initialized")
    
    async def close(self) -> None:
        """Close the HTTP clients."""
        await self._gamma_client.aclose()
        await self._clob_client.aclose()
    
    async def get_markets(
        self,
        limit: int = 100,
        offset: int = 0,
        active: bool = True,
        closed: bool = False
    ) -> list[PolymarketMarket]:
        """Get markets from Polymarket.
        
        Args:
            limit: Number of markets to return
            offset: Offset for pagination
            active: Include active markets
            closed: Include closed markets
            
        Returns:
            List of Polymarket markets
        """
        markets = []
        
        # Try CLOB API first (has better structure for active markets)
        try:
            # CLOB API returns active markets with proper token structure
            response = await self._clob_client.get("/markets", params={"limit": limit})
            
            if response.status_code == 200:
                data = response.json()
                
                # CLOB API returns {"data": [...], "next_cursor": "...", ...}
                markets_data = data.get("data", [])
                
                if isinstance(markets_data, list):
                    for market_data in markets_data:
                        # Skip archived markets (these are truly old)
                        if market_data.get("archived", False):
                            continue
                        
                        # For discovery purposes, include both active and closed markets
                        # since "closed" often just means betting has ended but market is recent
                        # Only skip if market has no active trading (accepting_orders = false AND no recent prices)
                            
                        try:
                            market = self._parse_market(market_data)
                            if market:
                                markets.append(market)
                        except Exception as e:
                            logger.debug(f"Error parsing CLOB market: {e}")
                    
                    logger.info(f"Retrieved {len(markets)} markets from Polymarket CLOB API")
                    return markets
                            
        except Exception as e:
            logger.debug(f"CLOB API failed, trying Gamma API: {e}")
        
        # Fallback to Gamma API
        try:
            params = {
                "limit": limit,
                "offset": offset,
                "active": str(active).lower(),
                "closed": str(closed).lower(),
            }
            
            # Use Gamma API for market discovery
            response = await self._gamma_client.get("/markets", params=params)
            
            if response.status_code != 200:
                logger.error(f"Polymarket Gamma API error: {response.status_code} {response.text}")
                return markets
            
            data = response.json()
            
            # Gamma API returns array directly
            markets_data = data if isinstance(data, list) else []
            
            for market_data in markets_data:
                try:
                    market = self._parse_market(market_data)
                    if market:
                        markets.append(market)
                except Exception as e:
                    logger.debug(f"Error parsing Gamma market: {e}")
            
            logger.info(f"Retrieved {len(markets)} markets from Polymarket Gamma API")
            return markets
            
        except Exception as e:
            logger.error(f"Error fetching Polymarket markets: {e}", exc_info=True)
            return markets
    
    async def get_live_soccer_markets(self) -> list[PolymarketMarket]:
        """Get live soccer markets using tag-based filtering."""
        all_soccer_markets = []
        
        # Soccer sport tag IDs from research
        soccer_tags = [
            82,      # EPL (Premier League)
            780,     # La Liga  
            1494,    # Bundesliga
            102070,  # Ligue 1
            101962,  # Serie A
            100977,  # Champions League
            1234,    # Champions League (alternate)
            101680,  # AFC
            102566,  # OFC
            102539,  # FIFA
            101735,  # Eredivisie
            102561,  # Argentina
            102008,  # Italian Cup
            102448,  # Mexico Liga MX
            102974   # Africa Cup of Nations
        ]
        
        logger.info(f"Fetching live soccer markets using {len(soccer_tags)} tag filters...")
        
        # Get markets for each soccer tag
        for tag_id in soccer_tags:
            try:
                response = await self._gamma_client.get("/markets", params={
                    "tag_id": tag_id,
                    "closed": "false",  # Only live markets
                    "limit": 50,
                    "offset": 0
                })
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if isinstance(data, list):
                        logger.info(f"Tag {tag_id}: Found {len(data)} live markets")
                        
                        for market_data in data:
                            try:
                                market = self._parse_market(market_data)
                                if market:
                                    all_soccer_markets.append(market)
                            except Exception as e:
                                logger.debug(f"Error parsing market for tag {tag_id}: {e}")
                    
                else:
                    logger.debug(f"Tag {tag_id} failed: {response.status_code}")
                
                # Rate limiting
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error fetching markets for tag {tag_id}: {e}")
                continue
        
        # Remove duplicates (same market might have multiple tags)
        unique_markets = {}
        for market in all_soccer_markets:
            unique_markets[market.condition_id] = market
        
        final_markets = list(unique_markets.values())
        logger.info(f"Found {len(final_markets)} unique live soccer markets")
        return final_markets
    
    async def get_soccer_markets(self) -> list[PolymarketMarket]:
        """Get all soccer-related markets (fallback method)."""
        return await self.get_live_soccer_markets()
    
    def _is_soccer_market(self, market: PolymarketMarket) -> bool:
        """Check if a market is soccer/football related."""
        text = f"{market.question} {market.description or ''} {market.category}".lower()
        
        # Soccer/football keywords  
        soccer_keywords = [
            "soccer", "football", "fifa", "uefa", "premier league", "epl",
            "bundesliga", "la liga", "serie a", "ligue 1", "champions league",
            "world cup", "euro", "match", "goal", "arsenal", "chelsea", "liverpool",
            "manchester", "barcelona", "real madrid", "bayern", "psg", "juventus",
            "win", "draw", "lose", "score"
        ]
        
        return any(keyword in text for keyword in soccer_keywords)
    
    def _parse_market(self, data: dict[str, Any]) -> PolymarketMarket | None:
        """Parse market data from Polymarket API response."""
        try:
            condition_id = data.get("condition_id") or data.get("conditionId")
            question = data.get("question") or data.get("title", "")
            market_slug = data.get("market_slug") or data.get("slug", "")
            
            if not condition_id or not question:
                return None
            
            # Parse end date
            end_date = None
            end_date_str = data.get("end_date_iso") or data.get("endDate") or data.get("end_time")
            if end_date_str:
                try:
                    end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                except Exception:
                    pass
            
            # Parse outcomes and tokens - handle different API structures
            outcomes = []
            outcome_prices = []
            tokens = []
            
            # Method 1: CLOB API structure (has tokens array directly)
            if "tokens" in data and isinstance(data["tokens"], list):
                for i, token_data in enumerate(data["tokens"]):
                    if isinstance(token_data, dict):
                        outcome_name = token_data.get("outcome", f"Outcome {i}")
                        price = float(token_data.get("price", 0.5))
                        token_id = str(token_data.get("token_id", f"token_{i}"))
                        
                        outcomes.append(outcome_name)
                        outcome_prices.append(price)
                        tokens.append(PolymarketToken(
                            token_id=token_id,
                            outcome=outcome_name,
                            price=price,
                            win_index=i
                        ))
            
            # Method 2: Gamma API structure (outcomes and outcomePrices as JSON strings)
            elif "outcomes" in data:
                import json
                
                # Handle outcomes (JSON string)
                outcomes_raw = data.get("outcomes")
                if isinstance(outcomes_raw, str):
                    try:
                        outcomes = json.loads(outcomes_raw)
                    except json.JSONDecodeError:
                        outcomes = ["Yes", "No"]  # Default
                elif isinstance(outcomes_raw, list):
                    outcomes = outcomes_raw
                else:
                    outcomes = ["Yes", "No"]  # Default
                
                # Handle outcome prices (JSON string)
                prices_raw = data.get("outcomePrices")
                if isinstance(prices_raw, str):
                    try:
                        price_strings = json.loads(prices_raw)
                        outcome_prices = [float(p) for p in price_strings]
                    except (json.JSONDecodeError, ValueError):
                        outcome_prices = [0.5] * len(outcomes)
                elif isinstance(prices_raw, list):
                    outcome_prices = [float(p) for p in prices_raw]
                else:
                    outcome_prices = [0.5] * len(outcomes)
                
                # Get token IDs (JSON string)
                token_ids_raw = data.get("clobTokenIds", "[]")
                if isinstance(token_ids_raw, str):
                    try:
                        token_ids = json.loads(token_ids_raw)
                    except json.JSONDecodeError:
                        token_ids = [f"token_{i}" for i in range(len(outcomes))]
                else:
                    token_ids = [f"token_{i}" for i in range(len(outcomes))]
                
                # Create tokens
                for i, outcome in enumerate(outcomes):
                    price = outcome_prices[i] if i < len(outcome_prices) else 0.5
                    token_id = token_ids[i] if i < len(token_ids) else f"token_{i}"
                    
                    tokens.append(PolymarketToken(
                        token_id=str(token_id),
                        outcome=outcome,
                        price=price,
                        win_index=i
                    ))
            
            # Fallback - create default structure
            if not outcomes:
                outcomes = ["Yes", "No"]
                outcome_prices = [0.5, 0.5]
                tokens = [
                    PolymarketToken(token_id="default_yes", outcome="Yes", price=0.5, win_index=0),
                    PolymarketToken(token_id="default_no", outcome="No", price=0.5, win_index=1)
                ]
            
            return PolymarketMarket(
                condition_id=str(condition_id),
                market_slug=market_slug,
                question=question,
                description=data.get("description", ""),
                category=data.get("category", ""),
                end_date_iso=end_date,
                outcomes=outcomes,
                outcome_prices=outcome_prices,
                tokens=tokens,
                raw_data=data
            )
            
        except Exception as e:
            logger.debug(f"Error parsing market data: {e}")
            return None


# For compatibility, keep the original PolymarketClient class
from src.clients.polymarket_client import PolymarketClient, PolymarketMarketData, PolymarketTokenData

# Import asyncio
import asyncio