#!/usr/bin/env python3
"""Quick live market matching - limited scope to avoid timeouts."""

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

async def quick_live_matching():
    """Quick live soccer market matching with limited scope."""
    
    print("🔍 QUICK Live Soccer Market Matching")
    print("=" * 40)
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Initialize clients
    kalshi_client = KalshiHttpClient(is_demo=False)  # Production
    polymarket_client = PolymarketDiscoveryClient()
    matcher = MarketMatcher()
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "kalshi_soccer_markets": [],
        "polymarket_soccer_markets": [],
        "matched_markets": []
    }
    
    try:
        # Step 1: Get LIMITED Kalshi soccer markets (no deep pagination)
        print("\n📊 Getting Kalshi soccer markets (LIMITED)...")
        
        # Get first batch only (500 markets max)
        sports_markets = await kalshi_client.get_markets(category="SPORTS", status="open", limit=500)
        print(f"Got {len(sports_markets)} Kalshi sports markets")
        
        # Filter for soccer
        kalshi_soccer = []
        for market in sports_markets:
            if kalshi_client._is_soccer_market(market):
                kalshi_soccer.append(market)
        
        print(f"✅ Found {len(kalshi_soccer)} Kalshi soccer markets")
        
        # Convert to dict and show samples
        kalshi_data = []
        for market in kalshi_soccer[:20]:  # Limit to first 20 for quick processing
            market_dict = {
                "ticker": market.ticker,
                "title": market.title,
                "yes_price": market.yes_price,
                "no_price": market.no_price,
                "status": market.status
            }
            kalshi_data.append(market_dict)
            
            # Show sample
            if len(kalshi_data) <= 5:
                print(f"   - {market.title}")
                print(f"     Ticker: {market.ticker}, Yes: ${market.yes_price:.3f}")
        
        results["kalshi_soccer_markets"] = kalshi_data
        
        # Step 2: Get LIMITED Polymarket soccer markets 
        print(f"\n🎯 Getting Polymarket soccer markets (tag-based, limited)...")
        
        # Test just a few key soccer tags
        key_soccer_tags = [82, 780, 1494, 100977]  # EPL, La Liga, Bundesliga, Champions League
        polymarket_soccer = []
        
        for tag_id in key_soccer_tags:
            try:
                response = await polymarket_client._gamma_client.get("/markets", params={
                    "tag_id": tag_id,
                    "closed": "false",
                    "limit": 10  # Small limit per tag
                })
                
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        print(f"Tag {tag_id}: Found {len(data)} markets")
                        for market_data in data:
                            try:
                                market = polymarket_client._parse_market(market_data)
                                if market:
                                    polymarket_soccer.append(market)
                            except Exception as e:
                                print(f"Parse error: {e}")
                
                await asyncio.sleep(0.2)  # Rate limiting
                
            except Exception as e:
                print(f"Tag {tag_id} error: {e}")
        
        # Remove duplicates
        unique_poly_markets = {}
        for market in polymarket_soccer:
            unique_poly_markets[market.condition_id] = market
        polymarket_soccer = list(unique_poly_markets.values())
        
        print(f"✅ Found {len(polymarket_soccer)} unique Polymarket soccer markets")
        
        # Convert and show samples
        polymarket_data = []
        for market in polymarket_soccer:
            market_dict = {
                "condition_id": market.condition_id,
                "question": market.question,
                "outcomes": market.outcomes,
                "outcome_prices": market.outcome_prices
            }
            polymarket_data.append(market_dict)
            
            # Show sample
            if len(polymarket_data) <= 5:
                print(f"   - {market.question}")
                print(f"     Outcomes: {market.outcomes}, Prices: {[f'${p:.3f}' for p in market.outcome_prices]}")
        
        results["polymarket_soccer_markets"] = polymarket_data
        
        # Step 3: Quick matching (limited scope)
        if kalshi_soccer and polymarket_soccer:
            print(f"\n🔗 Quick matching {len(kalshi_soccer)} Kalshi vs {len(polymarket_soccer)} Polymarket...")
            
            # Use only first 10 of each for quick matching
            kalshi_subset = kalshi_soccer[:10]
            polymarket_subset = polymarket_soccer[:10]
            
            matched_markets = matcher.find_matches(kalshi_subset, polymarket_subset)
            print(f"✅ Found {len(matched_markets)} matched pairs")
            
            # Convert matched markets
            matched_data = []
            for match in matched_markets:
                match_dict = {
                    "confidence": match.confidence,
                    "kalshi_ticker": match.kalshi_market.ticker,
                    "kalshi_title": match.kalshi_market.title,
                    "polymarket_question": match.polymarket_market.question,
                    "match_reason": match.match_reason
                }
                matched_data.append(match_dict)
                
                print(f"🎯 MATCH (Confidence: {match.confidence:.2f})")
                print(f"   Kalshi: {match.kalshi_market.title}")
                print(f"   Polymarket: {match.polymarket_market.question}")
                print(f"   Reason: {match.match_reason}")
                print()
            
            results["matched_markets"] = matched_data
        
        # Save results
        output_file = Path("quick_live_soccer_matches.json")
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n📋 QUICK MATCHING SUMMARY")
        print(f"═══════════════════════════")
        print(f"Kalshi soccer markets found: {len(kalshi_soccer)}")
        print(f"Polymarket soccer markets found: {len(polymarket_soccer)}")
        print(f"Matched pairs: {len(matched_markets) if 'matched_markets' in locals() else 0}")
        print(f"Results saved to: {output_file}")
        
        return results
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None
        
    finally:
        await kalshi_client.close()
        await polymarket_client.close()

if __name__ == "__main__":
    asyncio.run(quick_live_matching())