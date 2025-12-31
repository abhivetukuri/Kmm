#!/usr/bin/env python3
"""Debug what sports markets Kalshi actually has."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from src.clients.kalshi_http import KalshiHttpClient

async def debug_kalshi_sports():
    """Debug what sports markets Kalshi has."""
    
    print("🔍 Debugging Kalshi sports markets...")
    
    kalshi_client = KalshiHttpClient()
    
    try:
        # Get first 20 sports markets to see what they are
        response = await kalshi_client._client.get("/markets", params={
            "limit": 20,
            "category": "SPORTS", 
            "status": "open"
        })
        
        if response.status_code == 200:
            data = response.json()
            markets = data.get("markets", [])
            
            print(f"\n📊 KALSHI SPORTS MARKETS (first 20):")
            print(f"═══════════════════════════════════════")
            
            for i, market_data in enumerate(markets, 1):
                title = market_data.get("title", "No title")
                ticker = market_data.get("ticker", "No ticker")
                subtitle = market_data.get("subtitle", "")
                
                print(f"{i:2d}. {title}")
                print(f"    Ticker: {ticker}")
                if subtitle:
                    print(f"    Subtitle: {subtitle}")
                
                # Check if this could be soccer-related
                text = f"{title} {subtitle}".lower()
                soccer_keywords = [
                    "soccer", "football", "fifa", "uefa", "premier", "arsenal", "chelsea",
                    "liverpool", "manchester", "barcelona", "madrid", "bayern", "psg"
                ]
                
                if any(keyword in text for keyword in soccer_keywords):
                    print(f"    🟢 POTENTIAL SOCCER MATCH!")
                
                print()
                
        else:
            print(f"❌ Kalshi API error: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        await kalshi_client.close()

if __name__ == "__main__":
    asyncio.run(debug_kalshi_sports())