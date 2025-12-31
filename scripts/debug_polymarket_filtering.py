#!/usr/bin/env python3
"""Debug Polymarket filtering logic."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

from src.clients.polymarket_discovery import PolymarketDiscoveryClient

async def debug_filtering():
    """Debug why markets are being filtered out."""
    
    client = PolymarketDiscoveryClient()
    
    try:
        print("🔍 Debugging Polymarket market filtering...")
        
        # Test CLOB API directly
        response = await client._clob_client.get("/markets", params={"limit": 10})
        print(f"CLOB API Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            markets_data = data.get("data", [])
            
            print(f"Raw markets data length: {len(markets_data)}")
            
            # Check first few markets
            for i, market_data in enumerate(markets_data[:3]):
                print(f"\n--- Market {i+1} ---")
                print(f"Question: {market_data.get('question', 'N/A')}")
                print(f"Active: {market_data.get('active', 'N/A')}")
                print(f"Closed: {market_data.get('closed', 'N/A')}")
                print(f"Archived: {market_data.get('archived', 'N/A')}")
                
                # Test active filtering logic
                if True and not market_data.get("active", False):
                    print("❌ FILTERED OUT: Not active")
                    continue
                if not False and market_data.get("closed", False):
                    print("❌ FILTERED OUT: Market is closed")
                    continue
                
                # Test parsing
                try:
                    market = client._parse_market(market_data)
                    if market:
                        print("✅ Successfully parsed market")
                        print(f"   Outcomes: {market.outcomes}")
                        print(f"   Prices: {market.outcome_prices}")
                    else:
                        print("❌ Parsing returned None")
                except Exception as e:
                    print(f"❌ Parsing failed: {e}")
        
        # Test Gamma API as fallback
        print("\n🔄 Testing Gamma API...")
        response = await client._gamma_client.get("/markets", params={"limit": 5, "active": "true"})
        print(f"Gamma API Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Gamma markets length: {len(data) if isinstance(data, list) else 'Not list'}")
            
            if isinstance(data, list) and data:
                market_data = data[0]
                print(f"Sample question: {market_data.get('question')}")
                print(f"Sample outcomes: {market_data.get('outcomes')}")
                print(f"Sample prices: {market_data.get('outcomePrices')}")
                
                # Test parsing
                try:
                    market = client._parse_market(market_data)
                    if market:
                        print("✅ Gamma parsing successful")
                        print(f"   Outcomes: {market.outcomes}")
                        print(f"   Prices: {market.outcome_prices}")
                    else:
                        print("❌ Gamma parsing returned None")
                except Exception as e:
                    print(f"❌ Gamma parsing failed: {e}")
                    import traceback
                    traceback.print_exc()
    
    except Exception as e:
        print(f"❌ Debug error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(debug_filtering())