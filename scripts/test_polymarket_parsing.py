#!/usr/bin/env python3
"""Test the fixed Polymarket parsing."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.clients.polymarket_discovery import PolymarketDiscoveryClient

async def test_parsing():
    """Test Polymarket parsing."""
    client = PolymarketDiscoveryClient()
    
    try:
        print("🧪 Testing fixed Polymarket parsing...")
        
        # Test with small batch
        markets = await client.get_markets(limit=50, active=True)
        
        print(f"\n✅ Successfully parsed {len(markets)} markets!")
        
        # Show first few markets
        for i, market in enumerate(markets[:3], 1):
            print(f"\n{i}. {market.question}")
            print(f"   Slug: {market.market_slug}")
            print(f"   Outcomes: {market.outcomes}")
            print(f"   Prices: {market.outcome_prices}")
            print(f"   Tokens: {len(market.tokens)} tokens")
            for token in market.tokens:
                print(f"     - {token.outcome}: {token.token_id} (${token.price})")
        
        # Test soccer filtering
        soccer_markets = await client.get_soccer_markets()
        print(f"\n⚽ Found {len(soccer_markets)} soccer markets")
        
        # Show soccer markets
        for i, market in enumerate(soccer_markets[:3], 1):
            print(f"\n{i}. {market.question}")
            print(f"   Category: {market.category}")
            print(f"   Outcomes: {market.outcomes}")
            if market.end_date_iso:
                print(f"   End Date: {market.end_date_iso}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(test_parsing())