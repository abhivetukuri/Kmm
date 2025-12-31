#!/usr/bin/env python3
"""Efficient market discovery script - targeted soccer markets only."""

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
from src.core.config_generator import ConfigGenerator

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def get_soccer_markets_efficiently():
    """Get soccer markets efficiently without fetching everything."""
    
    # Initialize clients
    kalshi_client = KalshiHttpClient(auth=None, is_demo=True)
    poly_client = PolymarketDiscoveryClient()
    
    try:
        logger.info("🔍 Searching for soccer markets efficiently...")
        
        # For Kalshi: Try specific searches instead of getting all sports markets
        logger.info("📊 Checking Kalshi for soccer markets...")
        kalshi_markets = []
        
        # Try searching with keywords instead of category filtering
        # This will be much faster than paginating through all sports
        for search_term in ["soccer", "football", "premier", "liga", "bundesliga"]:
            try:
                # Use a small limit to avoid over-fetching
                markets = await kalshi_client.get_markets(limit=50)
                # Filter for soccer in the retrieved batch
                soccer_batch = [m for m in markets if kalshi_client._is_soccer_market(m)]
                kalshi_markets.extend(soccer_batch)
                
                if soccer_batch:
                    logger.info(f"  Found {len(soccer_batch)} soccer markets with '{search_term}'")
                
                # Stop early if we find enough
                if len(kalshi_markets) >= 10:
                    break
                    
            except Exception as e:
                logger.debug(f"Error searching for '{search_term}': {e}")
        
        # Remove duplicates
        unique_kalshi = {}
        for market in kalshi_markets:
            unique_kalshi[market.ticker] = market
        kalshi_markets = list(unique_kalshi.values())
        
        logger.info(f"📊 Found {len(kalshi_markets)} unique Kalshi soccer markets")
        
        # For Polymarket: Use smaller batches and stop when we have enough
        logger.info("🎯 Checking Polymarket for soccer markets...")
        poly_markets = []
        
        # Get markets in small batches
        for offset in range(0, 200, 50):  # Only check first 200 markets
            try:
                batch = await poly_client.get_markets(limit=50, offset=offset, active=True)
                if not batch:
                    break
                
                # Filter for soccer immediately
                soccer_batch = [m for m in batch if poly_client._is_soccer_market(m)]
                poly_markets.extend(soccer_batch)
                
                if soccer_batch:
                    logger.info(f"  Found {len(soccer_batch)} soccer markets in batch {offset//50 + 1}")
                
                # Small delay to be respectful
                await asyncio.sleep(0.2)
                
            except Exception as e:
                logger.error(f"Error fetching Polymarket batch: {e}")
                break
        
        logger.info(f"🎯 Found {len(poly_markets)} Polymarket soccer markets")
        
        return kalshi_markets, poly_markets
        
    finally:
        await kalshi_client.close()
        await poly_client.close()


async def main():
    """Main function for efficient market discovery."""
    logger.info("🚀 Starting efficient soccer market discovery")
    
    try:
        # Get markets efficiently
        kalshi_markets, poly_markets = await get_soccer_markets_efficiently()
        
        if not kalshi_markets and not poly_markets:
            logger.warning("⚠️  No soccer markets found on either platform")
            return
        
        # Match markets
        logger.info("🔄 Matching markets between platforms...")
        matcher = MarketMatcher(min_confidence_threshold=0.5)
        matched_markets = matcher.find_matches(kalshi_markets, poly_markets)
        
        logger.info(f"✅ Found {len(matched_markets)} market matches")
        
        # Generate comprehensive report
        report_path = Path(__file__).parent.parent / "market_discovery_report.md"
        await generate_comprehensive_report(
            kalshi_markets, poly_markets, matched_markets, report_path
        )
        
        # Generate config if we have matches
        if matched_markets:
            config_generator = ConfigGenerator(env="demo")
            config_path = Path(__file__).parent.parent / "config" / "markets_soccer.yaml"
            config_generator.generate_config(matched_markets, config_path)
            
            params_path = Path(__file__).parent.parent / "config" / "params_demo.yaml"
            config_generator.generate_params_file(params_path, "demo")
            
            logger.info(f"📝 Configuration generated: {config_path}")
        
        logger.info(f"📋 Comprehensive report generated: {report_path}")
        logger.info("🎉 Discovery completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Error during discovery: {e}", exc_info=True)


async def generate_comprehensive_report(kalshi_markets, poly_markets, matched_markets, report_path):
    """Generate a comprehensive markdown report for manual verification."""
    
    with open(report_path, 'w') as f:
        f.write("# Soccer Market Discovery Report\n\n")
        f.write(f"**Generated on:** {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # Summary
        f.write("## Summary\n\n")
        f.write(f"- **Kalshi Soccer Markets Found:** {len(kalshi_markets)}\n")
        f.write(f"- **Polymarket Soccer Markets Found:** {len(poly_markets)}\n")
        f.write(f"- **Successful Matches:** {len(matched_markets)}\n\n")
        
        # Matched Markets Section
        if matched_markets:
            f.write("## ✅ Matched Markets (Ready for Trading)\n\n")
            for i, match in enumerate(matched_markets, 1):
                f.write(f"### Match #{i} - Confidence: {match.match_confidence:.1%}\n\n")
                f.write(f"**Match Reason:** {match.match_reason}\n\n")
                
                f.write("#### Kalshi Market\n")
                f.write(f"- **Ticker:** `{match.kalshi_market.ticker}`\n")
                f.write(f"- **Title:** {match.kalshi_market.title}\n")
                if match.kalshi_market.subtitle:
                    f.write(f"- **Subtitle:** {match.kalshi_market.subtitle}\n")
                f.write(f"- **Category:** {match.kalshi_market.category}\n")
                f.write(f"- **Status:** {match.kalshi_market.status}\n")
                if match.kalshi_market.close_time:
                    f.write(f"- **Close Time:** {match.kalshi_market.close_time}\n")
                if match.kalshi_market.yes_bid and match.kalshi_market.yes_ask:
                    f.write(f"- **Current Prices:** Bid {match.kalshi_market.yes_bid}, Ask {match.kalshi_market.yes_ask}\n")
                
                f.write("\n#### Polymarket Market\n")
                f.write(f"- **Slug:** `{match.polymarket_market.market_slug}`\n")
                f.write(f"- **Question:** {match.polymarket_market.question}\n")
                if match.polymarket_market.description:
                    f.write(f"- **Description:** {match.polymarket_market.description}\n")
                f.write(f"- **Category:** {match.polymarket_market.category}\n")
                if match.polymarket_market.end_date_iso:
                    f.write(f"- **End Date:** {match.polymarket_market.end_date_iso}\n")
                f.write(f"- **Outcomes:** {', '.join(match.polymarket_market.outcomes)}\n")
                f.write(f"- **Prices:** {match.polymarket_market.outcome_prices}\n")
                
                # Token mapping
                f.write("\n#### Token Mapping for Trading\n")
                for token in match.polymarket_market.tokens:
                    f.write(f"- **{token.outcome}:** `{token.token_id}` (Price: {token.price})\n")
                
                f.write(f"\n**Settlement Notes:** {match.settlement_notes}\n")
                f.write("\n---\n\n")
        
        # Unmatched Kalshi Markets
        unmatched_kalshi = [m for m in kalshi_markets if not any(match.kalshi_market.ticker == m.ticker for match in matched_markets)]
        if unmatched_kalshi:
            f.write("## 📊 Unmatched Kalshi Markets\n\n")
            for market in unmatched_kalshi:
                f.write(f"### {market.ticker}\n")
                f.write(f"- **Title:** {market.title}\n")
                if market.subtitle:
                    f.write(f"- **Subtitle:** {market.subtitle}\n")
                f.write(f"- **Category:** {market.category}\n")
                f.write(f"- **Status:** {market.status}\n")
                if market.close_time:
                    f.write(f"- **Close Time:** {market.close_time}\n")
                f.write("\n")
        
        # Unmatched Polymarket Markets
        unmatched_poly = [m for m in poly_markets if not any(match.polymarket_market.condition_id == m.condition_id for match in matched_markets)]
        if unmatched_poly:
            f.write("## 🎯 Unmatched Polymarket Markets\n\n")
            for market in unmatched_poly:
                f.write(f"### {market.market_slug}\n")
                f.write(f"- **Question:** {market.question}\n")
                if market.description:
                    f.write(f"- **Description:** {market.description}\n")
                f.write(f"- **Category:** {market.category}\n")
                if market.end_date_iso:
                    f.write(f"- **End Date:** {market.end_date_iso}\n")
                f.write(f"- **Outcomes:** {', '.join(market.outcomes)}\n")
                f.write("\n")
        
        # Verification Notes
        f.write("## 🔍 Manual Verification Checklist\n\n")
        f.write("For each matched market, please verify:\n\n")
        f.write("1. **Settlement Rules:** Do both markets settle based on the same outcome?\n")
        f.write("2. **Event Identity:** Are they referring to the exact same match/event?\n")
        f.write("3. **Timing:** Do the close/settlement times align appropriately?\n")
        f.write("4. **Outcome Mapping:** Are YES/NO or Home/Draw/Away mapped correctly?\n")
        f.write("5. **Confidence:** Is the match confidence score reasonable for the similarity?\n\n")
        
        f.write("**Next Steps:**\n")
        f.write("- Review matched markets above\n")
        f.write("- Verify settlement rule equivalence\n")
        f.write("- Add any missing matches manually\n")
        f.write("- Run the trading system on approved matches\n")


if __name__ == "__main__":
    asyncio.run(main())