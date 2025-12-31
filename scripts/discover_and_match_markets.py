#!/usr/bin/env python3
"""Comprehensive market discovery and matching for verification."""

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


async def discover_and_match_markets():
    """Complete market discovery and matching process."""
    
    print("🔍 Starting comprehensive market discovery and matching...")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Initialize clients
    kalshi_client = KalshiHttpClient()
    polymarket_client = PolymarketDiscoveryClient()
    matcher = MarketMatcher()
    config_generator = ConfigGenerator()
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "kalshi_markets": [],
        "polymarket_markets": [],
        "matched_markets": [],
        "unmatched_kalshi": [],
        "unmatched_polymarket": [],
        "summary": {}
    }
    
    try:
        # Step 1: Discover Kalshi soccer markets
        print("\n📊 Discovering Kalshi soccer markets...")
        kalshi_markets = await kalshi_client.get_soccer_markets()
        print(f"✅ Found {len(kalshi_markets)} Kalshi soccer markets")
        
        # Convert to dict format for JSON serialization
        kalshi_markets_data = []
        for market in kalshi_markets:
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
        
        results["kalshi_markets"] = kalshi_markets_data
        
        # Step 2: Discover Polymarket soccer markets  
        print("\n🎯 Discovering Polymarket soccer markets...")
        polymarket_markets = await polymarket_client.get_soccer_markets()
        print(f"✅ Found {len(polymarket_markets)} Polymarket markets")
        
        # Filter for actual soccer markets (more precise filtering)
        actual_soccer_markets = []
        soccer_keywords = [
            "premier league", "epl", "bundesliga", "la liga", "serie a", "ligue 1",
            "champions league", "uefa", "fifa", "world cup", "euro 2024",
            "arsenal", "chelsea", "liverpool", "manchester", "barcelona", 
            "real madrid", "bayern", "psg", "juventus", "soccer", "football"
        ]
        
        for market in polymarket_markets:
            text = f"{market.question} {market.description or ''}".lower()
            # Check for actual soccer content (not just any "match" or "win")
            if any(keyword in text for keyword in soccer_keywords):
                # Additional filter: exclude obvious non-soccer content
                exclude_keywords = ["ncaab", "nba", "nfl", "nhl", "baseball", "basketball"]
                if not any(exclude in text for exclude in exclude_keywords):
                    actual_soccer_markets.append(market)
        
        polymarket_markets = actual_soccer_markets
        print(f"✅ Filtered to {len(polymarket_markets)} actual soccer markets")
        
        # Convert to dict format for JSON serialization
        polymarket_markets_data = []
        for market in polymarket_markets:
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
        
        results["polymarket_markets"] = polymarket_markets_data
        
        # Step 3: Match markets between platforms
        print("\n🔗 Matching markets between platforms...")
        matched_markets = matcher.find_matches(kalshi_markets, polymarket_markets)
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
        
        # Step 4: Identify unmatched markets
        matched_kalshi_tickers = {match.kalshi_market.ticker for match in matched_markets}
        matched_polymarket_ids = {match.polymarket_market.condition_id for match in matched_markets}
        
        unmatched_kalshi = [
            market for market in kalshi_markets 
            if market.ticker not in matched_kalshi_tickers
        ]
        unmatched_polymarket = [
            market for market in polymarket_markets
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
        
        # Step 5: Generate configuration
        print("\n⚙️ Generating market configuration...")
        config_file = config_generator.generate_config(matched_markets)
        print(f"✅ Generated configuration: {config_file}")
        
        # Step 6: Summary statistics
        results["summary"] = {
            "kalshi_markets_found": len(kalshi_markets),
            "polymarket_markets_found": len(polymarket_markets),
            "matched_pairs": len(matched_markets),
            "unmatched_kalshi": len(unmatched_kalshi),
            "unmatched_polymarket": len(unmatched_polymarket),
            "match_rate": len(matched_markets) / max(len(kalshi_markets), len(polymarket_markets)) * 100 if kalshi_markets or polymarket_markets else 0,
            "config_file_generated": str(config_file)
        }
        
        # Step 7: Save detailed results
        output_file = Path("market_discovery_results.json")
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n📋 SUMMARY")
        print(f"═══════════")
        print(f"Kalshi soccer markets: {results['summary']['kalshi_markets_found']}")
        print(f"Polymarket soccer markets: {results['summary']['polymarket_markets_found']}")
        print(f"Matched market pairs: {results['summary']['matched_pairs']}")
        print(f"Unmatched Kalshi markets: {results['summary']['unmatched_kalshi']}")
        print(f"Unmatched Polymarket markets: {results['summary']['unmatched_polymarket']}")
        print(f"Match rate: {results['summary']['match_rate']:.1f}%")
        print(f"Configuration file: {results['summary']['config_file_generated']}")
        print(f"Detailed results saved to: {output_file}")
        
        # Show top matches for verification
        print(f"\n🎯 TOP MATCHED MARKETS (for verification)")
        print(f"════════════════════════════════════════")
        for i, match in enumerate(matched_markets[:5], 1):
            print(f"\n{i}. MATCH (Confidence: {match.confidence:.2f})")
            print(f"   Kalshi: {match.kalshi_market.title}")
            print(f"   ↳ Ticker: {match.kalshi_market.ticker}, Yes: ${match.kalshi_market.yes_price:.3f}")
            print(f"   Polymarket: {match.polymarket_market.question}")
            print(f"   ↳ Outcomes: {match.polymarket_market.outcomes}")
            print(f"   ↳ Prices: {[f'${p:.3f}' for p in match.polymarket_market.outcome_prices]}")
            print(f"   Reason: {match.match_reason}")
        
        return results
        
    except Exception as e:
        print(f"❌ Error during discovery and matching: {e}")
        import traceback
        traceback.print_exc()
        return None
        
    finally:
        # Clean up
        await kalshi_client.close()
        await polymarket_client.close()


if __name__ == "__main__":
    asyncio.run(discover_and_match_markets())