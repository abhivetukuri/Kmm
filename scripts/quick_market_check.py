#!/usr/bin/env python3
"""Quick market check - just get a small sample to verify matching works."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.clients.kalshi_http import KalshiHttpClient
from src.clients.polymarket_discovery import PolymarketDiscoveryClient
from src.core.market_matcher import MarketMatcher

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


async def quick_market_sample():
    """Get just a small sample of markets to test matching."""
    
    # Initialize clients
    kalshi_client = KalshiHttpClient(auth=None, is_demo=True)
    poly_client = PolymarketDiscoveryClient()
    
    try:
        logger.info("🔍 Getting small sample of markets...")
        
        # Get just 20 markets from Kalshi to start
        logger.info("📊 Getting Kalshi sample (limit 20)...")
        all_kalshi = await kalshi_client.get_markets(limit=20)
        kalshi_markets = [m for m in all_kalshi if kalshi_client._is_soccer_market(m)]
        logger.info(f"📊 Found {len(kalshi_markets)} soccer markets in Kalshi sample")
        
        # Get 100 markets from Polymarket
        logger.info("🎯 Getting Polymarket sample (limit 100)...")
        all_poly = await poly_client.get_markets(limit=100, active=True)
        poly_markets = [m for m in all_poly if poly_client._is_soccer_market(m)]
        logger.info(f"🎯 Found {len(poly_markets)} soccer markets in Polymarket sample")
        
        return kalshi_markets, poly_markets
        
    finally:
        await kalshi_client.close()
        await poly_client.close()


def print_market_sample(kalshi_markets, poly_markets):
    """Print sample of markets found."""
    
    print("\n" + "="*60)
    print("📊 KALSHI SOCCER MARKETS SAMPLE")
    print("="*60)
    
    for i, market in enumerate(kalshi_markets[:5], 1):
        print(f"\n{i}. {market.ticker}")
        print(f"   Title: {market.title}")
        if market.subtitle:
            print(f"   Subtitle: {market.subtitle}")
        print(f"   Category: {market.category}")
        print(f"   Status: {market.status}")
        if market.close_time:
            print(f"   Close: {market.close_time}")
        if market.yes_bid and market.yes_ask:
            print(f"   Prices: Bid {market.yes_bid} / Ask {market.yes_ask}")
    
    if len(kalshi_markets) > 5:
        print(f"\n   ... and {len(kalshi_markets) - 5} more")
    
    print("\n" + "="*60)
    print("🎯 POLYMARKET SOCCER MARKETS SAMPLE")
    print("="*60)
    
    for i, market in enumerate(poly_markets[:5], 1):
        print(f"\n{i}. {market.market_slug}")
        print(f"   Question: {market.question}")
        if market.description:
            print(f"   Description: {market.description}")
        print(f"   Category: {market.category}")
        if market.end_date_iso:
            print(f"   End Date: {market.end_date_iso}")
        print(f"   Outcomes: {', '.join(market.outcomes)}")
        print(f"   Prices: {market.outcome_prices}")
    
    if len(poly_markets) > 5:
        print(f"\n   ... and {len(poly_markets) - 5} more")


async def main():
    """Main function."""
    logger.info("🚀 Quick market sample and matching test")
    
    try:
        # Get small sample
        kalshi_markets, poly_markets = await quick_market_sample()
        
        # Print what we found
        print_market_sample(kalshi_markets, poly_markets)
        
        # Try matching
        if kalshi_markets and poly_markets:
            logger.info("\n🔄 Testing market matching...")
            matcher = MarketMatcher(min_confidence_threshold=0.3)  # Lower threshold for testing
            matched_markets = matcher.find_matches(kalshi_markets, poly_markets)
            
            print("\n" + "="*60)
            print("✅ MATCHED MARKETS")
            print("="*60)
            
            if matched_markets:
                for i, match in enumerate(matched_markets, 1):
                    print(f"\n{i}. MATCH - Confidence: {match.match_confidence:.1%}")
                    print(f"   Kalshi: {match.kalshi_market.ticker}")
                    print(f"     → {match.kalshi_market.title}")
                    print(f"   Polymarket: {match.polymarket_market.market_slug}")
                    print(f"     → {match.polymarket_market.question}")
                    print(f"   Reason: {match.match_reason}")
                    
                    # Show token mapping for trading
                    print(f"   Trading Tokens:")
                    for token in match.polymarket_market.tokens:
                        print(f"     {token.outcome}: {token.token_id} (${token.price})")
            else:
                print("\n❌ No matches found")
                print("\nThis could mean:")
                print("- Markets are too different")
                print("- Need to adjust matching algorithm")
                print("- Small sample doesn't contain matching pairs")
        else:
            print("\n❌ No soccer markets found in sample")
            print("Kalshi demo might not have soccer markets")
            print("Polymarket sample might be too small")
        
        print("\n" + "="*60)
        print("📋 SUMMARY")
        print("="*60)
        print(f"Kalshi soccer markets: {len(kalshi_markets)}")
        print(f"Polymarket soccer markets: {len(poly_markets)}")
        if kalshi_markets and poly_markets:
            print(f"Successful matches: {len(matched_markets)}")
        
        print("\n✅ Quick sample completed!")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())