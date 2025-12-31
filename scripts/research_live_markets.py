#!/usr/bin/env python3
"""Research live markets on both Polymarket and Kalshi production."""

from __future__ import annotations

import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
import httpx

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def research_polymarket_sports():
    """Research Polymarket sports tags and live markets."""
    
    print("🔍 Researching Polymarket live sports markets...")
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            # 1. Get sports metadata and tag IDs
            print("\n📊 Getting sports metadata...")
            sports_response = await client.get("https://gamma-api.polymarket.com/sports")
            
            if sports_response.status_code == 200:
                sports_data = sports_response.json()
                print(f"✅ Found {len(sports_data)} sports categories")
                
                # Find soccer/football tags
                soccer_tags = []
                for sport in sports_data:
                    name = sport.get("name", "").lower()
                    if any(keyword in name for keyword in ["soccer", "football", "fifa", "premier", "uefa"]):
                        soccer_tags.append(sport)
                        print(f"🟢 Soccer sport found: {sport.get('name')} (ID: {sport.get('tag_id')})")
                
                # Save sports data
                with open("polymarket_sports_metadata.json", "w") as f:
                    json.dump(sports_data, f, indent=2)
                    
            else:
                print(f"❌ Sports API error: {sports_response.status_code}")
                soccer_tags = []
            
            # 2. Get live markets (general)
            print("\n📈 Getting live markets...")
            markets_response = await client.get("https://gamma-api.polymarket.com/markets", params={
                "closed": "false",
                "limit": 50,
                "offset": 0
            })
            
            if markets_response.status_code == 200:
                markets_data = markets_response.json()
                print(f"✅ Found {len(markets_data)} live markets")
                
                # Filter for soccer markets
                soccer_markets = []
                soccer_keywords = [
                    "soccer", "football", "fifa", "uefa", "premier league", "epl",
                    "bundesliga", "la liga", "serie a", "ligue 1", "champions league",
                    "world cup", "euro", "arsenal", "chelsea", "liverpool",
                    "manchester", "barcelona", "real madrid", "bayern", "psg", "juventus"
                ]
                
                for market in markets_data:
                    text = f"{market.get('question', '')} {market.get('description', '')}".lower()
                    if any(keyword in text for keyword in soccer_keywords):
                        soccer_markets.append(market)
                        print(f"⚽ Live soccer market: {market.get('question', 'N/A')[:80]}...")
                
                print(f"✅ Found {len(soccer_markets)} live soccer markets")
                
                # Save live soccer markets
                if soccer_markets:
                    with open("polymarket_live_soccer_markets.json", "w") as f:
                        json.dump(soccer_markets, f, indent=2)
                        
            else:
                print(f"❌ Markets API error: {markets_response.status_code}")
                soccer_markets = []
            
            # 3. Try specific soccer tag filtering if we found tags
            if soccer_tags:
                print(f"\n🎯 Testing tag-based filtering...")
                for tag in soccer_tags[:2]:  # Test first 2 soccer tags
                    tag_id = tag.get("tag_id")
                    tag_name = tag.get("name")
                    
                    tag_response = await client.get("https://gamma-api.polymarket.com/markets", params={
                        "tag_id": tag_id,
                        "closed": "false",
                        "limit": 20
                    })
                    
                    if tag_response.status_code == 200:
                        tag_markets = tag_response.json()
                        print(f"✅ Tag '{tag_name}' (ID: {tag_id}): {len(tag_markets)} live markets")
                        
                        for market in tag_markets[:3]:  # Show first 3
                            print(f"   - {market.get('question', 'N/A')[:60]}...")
                    else:
                        print(f"❌ Tag {tag_id} error: {tag_response.status_code}")
            
            return {
                "soccer_tags": soccer_tags,
                "live_soccer_markets": soccer_markets if 'soccer_markets' in locals() else [],
                "total_live_markets": len(markets_data) if 'markets_data' in locals() else 0
            }
            
        except Exception as e:
            print(f"❌ Error researching Polymarket: {e}")
            import traceback
            traceback.print_exc()
            return None

async def research_kalshi_production():
    """Research Kalshi production sports markets."""
    
    print("\n🔍 Researching Kalshi production sports markets...")
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            # Try Kalshi production API
            prod_url = "https://trading-api.kalshi.com/trade-api/v2"
            
            # Get sports markets
            response = await client.get(f"{prod_url}/markets", params={
                "limit": 100,
                "category": "SPORTS",
                "status": "open"
            })
            
            if response.status_code == 200:
                data = response.json()
                markets = data.get("markets", [])
                print(f"✅ Found {len(markets)} live Kalshi sports markets")
                
                # Filter for soccer markets
                soccer_markets = []
                soccer_keywords = [
                    "soccer", "football", "fifa", "uefa", "premier", "arsenal", "chelsea",
                    "liverpool", "manchester", "barcelona", "madrid", "bayern", "psg"
                ]
                
                for market in markets:
                    title = market.get("title", "")
                    subtitle = market.get("subtitle", "")
                    text = f"{title} {subtitle}".lower()
                    
                    if any(keyword in text for keyword in soccer_keywords):
                        soccer_markets.append(market)
                        print(f"⚽ Live Kalshi soccer market: {title}")
                
                print(f"✅ Found {len(soccer_markets)} live Kalshi soccer markets")
                
                # Show sample of all sports markets for context
                print(f"\n📊 Sample Kalshi sports markets:")
                for i, market in enumerate(markets[:5], 1):
                    print(f"{i}. {market.get('title', 'N/A')}")
                
                # Save results
                if soccer_markets:
                    with open("kalshi_live_soccer_markets.json", "w") as f:
                        json.dump(soccer_markets, f, indent=2)
                        
                return {
                    "live_soccer_markets": soccer_markets,
                    "total_sports_markets": len(markets),
                    "sample_sports_markets": markets[:10]
                }
                
            else:
                print(f"❌ Kalshi production API error: {response.status_code}")
                # Try to get more info about the error
                try:
                    error_data = response.json()
                    print(f"Error details: {error_data}")
                except:
                    print(f"Error text: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error researching Kalshi production: {e}")
            import traceback
            traceback.print_exc()
            return None

async def main():
    """Research live markets on both platforms."""
    
    print("🔍 RESEARCH: Live Sports Markets on Both Platforms")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Research both platforms
    polymarket_results = await research_polymarket_sports()
    kalshi_results = await research_kalshi_production()
    
    # Summary
    print(f"\n📋 RESEARCH SUMMARY")
    print(f"=" * 30)
    
    if polymarket_results:
        poly_soccer = len(polymarket_results["live_soccer_markets"])
        poly_total = polymarket_results["total_live_markets"]
        print(f"Polymarket: {poly_soccer} live soccer markets out of {poly_total} total")
    else:
        print("Polymarket: Research failed")
    
    if kalshi_results:
        kalshi_soccer = len(kalshi_results["live_soccer_markets"])
        kalshi_total = kalshi_results["total_sports_markets"]
        print(f"Kalshi: {kalshi_soccer} live soccer markets out of {kalshi_total} sports markets")
    else:
        print("Kalshi: Research failed (may need authentication)")
    
    # Save combined results
    results = {
        "timestamp": datetime.now().isoformat(),
        "polymarket": polymarket_results,
        "kalshi": kalshi_results
    }
    
    with open("live_markets_research.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n✅ Research complete - results saved to live_markets_research.json")

if __name__ == "__main__":
    asyncio.run(main())