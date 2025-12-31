#!/usr/bin/env python3
"""Live market discovery and matching between Kalshi and Polymarket."""

from __future__ import annotations

import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from src.clients.kalshi_http import KalshiHttpClient
from src.clients.polymarket_discovery import PolymarketDiscoveryClient
from src.core.market_matcher import MarketMatcher
from src.core.config_generator import ConfigGenerator

async def discover_live_markets():
    """Discover live soccer markets from both platforms and match them."""
    
    print("🔍 Starting LIVE soccer market discovery and matching...")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)
    
    # Initialize clients
    kalshi_client = KalshiHttpClient(is_demo=False)  # Use production
    polymarket_client = PolymarketDiscoveryClient()
    matcher = MarketMatcher()
    config_generator = ConfigGenerator()
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "kalshi_live_soccer_markets": [],
        "polymarket_live_soccer_markets": [],
        "matched_markets": [],
        "unmatched_kalshi": [],
        "unmatched_polymarket": [],
        "summary": {}
    }
    
    try:
        # Step 1: Get live soccer markets from Kalshi production
        print("\n📊 Discovering live soccer markets from Kalshi PRODUCTION...")
        kalshi_soccer_markets = await kalshi_client.get_live_soccer_markets()
        print(f"✅ Found {len(kalshi_soccer_markets)} live Kalshi soccer markets")
        
        # Convert to dict for serialization
        kalshi_markets_data = []
        for market in kalshi_soccer_markets:
            market_dict = {
                "ticker": market.ticker,
                "title": market.title,
                "subtitle": market.subtitle,
                "close_time": market.close_time.isoformat() if market.close_time else None,
                "yes_price": market.yes_price,
                "no_price": market.no_price,
                "status": market.status,
                "category": market.category
            }
            kalshi_markets_data.append(market_dict)
        
        results["kalshi_live_soccer_markets"] = kalshi_markets_data
        
        # Show sample Kalshi markets
        if kalshi_soccer_markets:
            print(f"\n🎯 SAMPLE KALSHI LIVE SOCCER MARKETS:")
            for i, market in enumerate(kalshi_soccer_markets[:5], 1):
                print(f"{i}. {market.title}")
                print(f"   Ticker: {market.ticker}")
                print(f"   Yes: ${market.yes_price:.3f}, No: ${market.no_price:.3f}")
                print(f"   Status: {market.status}")
        
        # Step 2: Get live soccer markets from Polymarket using tag filtering
        print(f"\n🎯 Discovering live soccer markets from Polymarket (tag-based)...")
        polymarket_soccer_markets = await polymarket_client.get_live_soccer_markets()
        print(f"✅ Found {len(polymarket_soccer_markets)} live Polymarket soccer markets")
        
        # Convert to dict for serialization
        polymarket_markets_data = []
        for market in polymarket_soccer_markets:
            market_dict = {
                "condition_id": market.condition_id,
                "question": market.question,
                "market_slug": market.market_slug,
                "description": market.description,
                "category": market.category,
                "end_date_iso": market.end_date_iso.isoformat() if market.end_date_iso else None,
                "outcomes": market.outcomes,
                "outcome_prices": market.outcome_prices
            }
            polymarket_markets_data.append(market_dict)
        
        results["polymarket_live_soccer_markets"] = polymarket_markets_data
        
        # Show sample Polymarket markets
        if polymarket_soccer_markets:
            print(f"\n🎯 SAMPLE POLYMARKET LIVE SOCCER MARKETS:")
            for i, market in enumerate(polymarket_soccer_markets[:5], 1):
                print(f"{i}. {market.question}")
                print(f"   Outcomes: {market.outcomes}")
                print(f"   Prices: {[f'${p:.3f}' for p in market.outcome_prices]}")
                print(f"   End Date: {market.end_date_iso}")
        
        # Step 3: Market matching
        if kalshi_soccer_markets and polymarket_soccer_markets:
            print(f"\n🔗 Matching {len(kalshi_soccer_markets)} Kalshi markets with {len(polymarket_soccer_markets)} Polymarket markets...")
            matched_markets = matcher.find_matches(kalshi_soccer_markets, polymarket_soccer_markets)
            print(f"✅ Found {len(matched_markets)} matched market pairs")
            
            # Convert matched markets to dict format
            matched_markets_data = []
            for match in matched_markets:
                match_dict = {
                    "confidence": match.confidence,
                    "kalshi_market": {
                        "ticker": match.kalshi_market.ticker,
                        "title": match.kalshi_market.title,
                        "yes_price": match.kalshi_market.yes_price,
                        "no_price": match.kalshi_market.no_price
                    },
                    "polymarket_market": {
                        "condition_id": match.polymarket_market.condition_id,
                        "question": match.polymarket_market.question,
                        "outcomes": match.polymarket_market.outcomes,
                        "outcome_prices": match.polymarket_market.outcome_prices
                    },
                    "match_reason": match.match_reason
                }
                matched_markets_data.append(match_dict)
            
            results["matched_markets"] = matched_markets_data
            
            # Identify unmatched markets
            matched_kalshi_tickers = {match.kalshi_market.ticker for match in matched_markets}
            matched_polymarket_ids = {match.polymarket_market.condition_id for match in matched_markets}
            
            unmatched_kalshi = [
                market for market in kalshi_soccer_markets
                if market.ticker not in matched_kalshi_tickers
            ]
            unmatched_polymarket = [
                market for market in polymarket_soccer_markets
                if market.condition_id not in matched_polymarket_ids
            ]
            
            results["unmatched_kalshi"] = [
                {"ticker": market.ticker, "title": market.title}
                for market in unmatched_kalshi
            ]
            results["unmatched_polymarket"] = [
                {"condition_id": market.condition_id, "question": market.question}
                for market in unmatched_polymarket
            ]
            
            # Generate configuration if matches found
            if matched_markets:
                print(f"\n⚙️ Generating market configuration for {len(matched_markets)} matches...")
                config_file = config_generator.generate_config(matched_markets)
                print(f"✅ Generated configuration: {config_file}")
            
        else:
            print(f"\n❌ Cannot match markets - missing data from one or both platforms")
            matched_markets = []
            unmatched_kalshi = kalshi_soccer_markets
            unmatched_polymarket = polymarket_soccer_markets
        
        # Summary
        results["summary"] = {
            "kalshi_live_soccer_markets": len(kalshi_soccer_markets),
            "polymarket_live_soccer_markets": len(polymarket_soccer_markets),
            "matched_pairs": len(matched_markets) if matched_markets else 0,
            "unmatched_kalshi": len(kalshi_soccer_markets) - (len(matched_markets) if matched_markets else 0),
            "unmatched_polymarket": len(polymarket_soccer_markets) - (len(matched_markets) if matched_markets else 0),
            "match_rate": (len(matched_markets) / max(len(kalshi_soccer_markets), len(polymarket_soccer_markets)) * 100) if (matched_markets and (kalshi_soccer_markets or polymarket_soccer_markets)) else 0,
            "api_efficiency": "Tag-based filtering used for Polymarket, production API for Kalshi"
        }
        
        # Save results
        output_file = Path("live_soccer_market_matches.json")
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n📋 LIVE MARKET MATCHING RESULTS")
        print(f"═══════════════════════════════")
        print(f"Kalshi live soccer markets: {results['summary']['kalshi_live_soccer_markets']}")
        print(f"Polymarket live soccer markets: {results['summary']['polymarket_live_soccer_markets']}")
        print(f"Matched market pairs: {results['summary']['matched_pairs']}")
        print(f"Unmatched Kalshi markets: {results['summary']['unmatched_kalshi']}")
        print(f"Unmatched Polymarket markets: {results['summary']['unmatched_polymarket']}")
        print(f"Match rate: {results['summary']['match_rate']:.1f}%")
        print(f"Results saved to: {output_file}")
        
        # Show matched markets for verification
        if matched_markets:
            print(f"\n🎯 MATCHED LIVE MARKETS (for verification)")
            print(f"═════════════════════════════════════")
            for i, match in enumerate(matched_markets, 1):
                print(f"\n{i}. MATCH (Confidence: {match.confidence:.2f})")
                print(f"   Kalshi: {match.kalshi_market.title}")
                print(f"   ↳ Ticker: {match.kalshi_market.ticker}")
                print(f"   ↳ Prices: Yes ${match.kalshi_market.yes_price:.3f}, No ${match.kalshi_market.no_price:.3f}")
                print(f"   Polymarket: {match.polymarket_market.question}")
                print(f"   ↳ Outcomes: {match.polymarket_market.outcomes}")
                print(f"   ↳ Prices: {[f'${p:.3f}' for p in match.polymarket_market.outcome_prices]}")
                print(f"   Reason: {match.match_reason}")
        
        return results
        
    except Exception as e:
        print(f"❌ Error during live market discovery and matching: {e}")
        import traceback
        traceback.print_exc()
        return None
        
    finally:
        # Clean up
        await kalshi_client.close()
        await polymarket_client.close()

if __name__ == "__main__":
    asyncio.run(discover_live_markets())