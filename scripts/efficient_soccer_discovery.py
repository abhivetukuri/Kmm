#!/usr/bin/env python3
"""Efficient soccer market discovery and matching - LIMITED API calls."""

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

async def efficient_soccer_discovery():
    """Efficient soccer market discovery with limited API calls."""
    
    print("🔍 Starting EFFICIENT soccer market discovery...")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Initialize clients
    kalshi_client = KalshiHttpClient()
    polymarket_client = PolymarketDiscoveryClient()
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "kalshi_markets": [],
        "polymarket_markets": [],
        "matched_markets": [],
        "summary": {}
    }
    
    try:
        # Step 1: Get LIMITED Kalshi markets (only first 100 sports markets)
        print("\n📊 Discovering Kalshi markets (LIMITED to 100)...")
        
        # Make a single targeted API call
        response = await kalshi_client._client.get("/markets", params={
            "limit": 100,  # Only 100 markets
            "category": "SPORTS",
            "status": "open"
        })
        
        if response.status_code == 200:
            data = response.json()
            all_kalshi_markets = []
            
            for market_data in data.get("markets", []):
                try:
                    market = kalshi_client._parse_market(market_data)
                    if market:
                        all_kalshi_markets.append(market)
                except Exception as e:
                    print(f"Error parsing Kalshi market: {e}")
                    continue
            
            # Filter for soccer-related markets
            soccer_keywords = [
                "soccer", "football", "fifa", "uefa", "premier", "arsenal", "chelsea",
                "liverpool", "manchester", "barcelona", "madrid", "bayern", "psg"
            ]
            
            kalshi_soccer = []
            for market in all_kalshi_markets:
                text = f"{market.title} {market.subtitle or ''}".lower()
                if any(keyword in text for keyword in soccer_keywords):
                    kalshi_soccer.append(market)
            
            print(f"✅ Found {len(kalshi_soccer)} Kalshi soccer markets out of {len(all_kalshi_markets)} total sports markets")
            
            # Convert to dict format
            kalshi_markets_data = []
            for market in kalshi_soccer:
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
            
        else:
            print(f"❌ Kalshi API error: {response.status_code}")
            kalshi_soccer = []
        
        # Step 2: Get LIMITED Polymarket markets 
        print("\n🎯 Discovering Polymarket markets (LIMITED to 50)...")
        
        polymarket_markets = await polymarket_client.get_markets(limit=50, active=True)
        print(f"Got {len(polymarket_markets)} total Polymarket markets")
        
        # Filter for ACTUAL soccer markets (more precise)
        actual_soccer_keywords = [
            "premier league", "bundesliga", "la liga", "serie a", "ligue 1",
            "champions league", "uefa", "fifa", "world cup", "euro",
            "arsenal", "chelsea", "liverpool", "manchester united", "manchester city",
            "barcelona", "real madrid", "bayern", "psg", "juventus"
        ]
        
        polymarket_soccer = []
        for market in polymarket_markets:
            text = f"{market.question} {market.description or ''}".lower()
            # Must contain actual soccer keywords AND exclude obvious non-soccer
            if any(keyword in text for keyword in actual_soccer_keywords):
                exclude_keywords = ["ncaab", "nba", "nfl", "nhl", "baseball", "basketball", "tennis"]
                if not any(exclude in text for exclude in exclude_keywords):
                    polymarket_soccer.append(market)
        
        print(f"✅ Filtered to {len(polymarket_soccer)} actual Polymarket soccer markets")
        
        # Convert to dict format
        polymarket_markets_data = []
        for market in polymarket_soccer:
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
        
        # Step 3: Match markets (if any found)
        if kalshi_soccer and polymarket_soccer:
            print("\n🔗 Matching markets between platforms...")
            matcher = MarketMatcher()
            matched_markets = matcher.find_matches(kalshi_soccer, polymarket_soccer)
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
            
            # Generate configuration if matches found
            if matched_markets:
                print("\n⚙️ Generating market configuration...")
                config_generator = ConfigGenerator()
                config_file = config_generator.generate_config(matched_markets)
                print(f"✅ Generated configuration: {config_file}")
                
        else:
            print("\n❌ No soccer markets found on one or both platforms")
            matched_markets = []
        
        # Summary
        results["summary"] = {
            "kalshi_soccer_markets": len(kalshi_soccer) if kalshi_soccer else 0,
            "polymarket_soccer_markets": len(polymarket_soccer) if polymarket_soccer else 0,
            "matched_pairs": len(matched_markets) if matched_markets else 0,
            "api_calls_made": "2 (1 Kalshi + 1 Polymarket)",
            "efficiency_note": "Limited discovery to reduce API calls"
        }
        
        # Save results
        output_file = Path("efficient_soccer_discovery_results.json")
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n📋 EFFICIENT DISCOVERY RESULTS")
        print(f"═══════════════════════════════")
        print(f"Kalshi soccer markets: {results['summary']['kalshi_soccer_markets']}")
        print(f"Polymarket soccer markets: {results['summary']['polymarket_soccer_markets']}")
        print(f"Matched market pairs: {results['summary']['matched_pairs']}")
        print(f"API calls made: {results['summary']['api_calls_made']}")
        print(f"Results saved to: {output_file}")
        
        # Show sample markets
        if kalshi_soccer:
            print(f"\n🎯 SAMPLE KALSHI SOCCER MARKETS")
            print(f"═══════════════════════════════")
            for i, market in enumerate(kalshi_soccer[:3], 1):
                print(f"{i}. {market.title}")
                print(f"   Ticker: {market.ticker}")
                print(f"   Yes: ${market.yes_price:.3f}, No: ${market.no_price:.3f}")
        
        if polymarket_soccer:
            print(f"\n🎯 SAMPLE POLYMARKET SOCCER MARKETS")
            print(f"═══════════════════════════════")
            for i, market in enumerate(polymarket_soccer[:3], 1):
                print(f"{i}. {market.question}")
                print(f"   Outcomes: {market.outcomes}")
                print(f"   Prices: {[f'${p:.3f}' for p in market.outcome_prices]}")
        
        if matched_markets:
            print(f"\n🎯 MATCHED MARKETS")
            print(f"═══════════════════════════════")
            for i, match in enumerate(matched_markets, 1):
                print(f"\n{i}. MATCH (Confidence: {match.confidence:.2f})")
                print(f"   Kalshi: {match.kalshi_market.title}")
                print(f"   Polymarket: {match.polymarket_market.question}")
                print(f"   Reason: {match.match_reason}")
        
        return results
        
    except Exception as e:
        print(f"❌ Error during efficient discovery: {e}")
        import traceback
        traceback.print_exc()
        return None
        
    finally:
        # Clean up
        await kalshi_client.close()
        await polymarket_client.close()

if __name__ == "__main__":
    asyncio.run(efficient_soccer_discovery())