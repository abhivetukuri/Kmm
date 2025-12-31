#!/usr/bin/env python3
"""Simple test of market discovery and matching without API calls."""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.types import KalshiMarket, PolymarketMarket, PolymarketToken
from src.core.market_matcher import MarketMatcher
from src.core.config_generator import ConfigGenerator

# Setup logging
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def create_sample_markets():
    """Create sample markets for testing."""
    
    # Sample Kalshi markets
    kalshi_markets = [
        KalshiMarket(
            ticker="SOCCEREPL-24DEC-ARS",
            title="Arsenal will beat Chelsea in Premier League on Dec 24",
            subtitle="EPL Match",
            category="SPORTS",
            status="open",
            yes_ask=0.52,
            yes_bid=0.48,
            no_ask=0.52,
            no_bid=0.48,
            open_time=datetime(2024, 12, 20, tzinfo=timezone.utc),
            close_time=datetime(2024, 12, 24, 15, 0, tzinfo=timezone.utc),
            settle_time=datetime(2024, 12, 24, 17, 0, tzinfo=timezone.utc),
            raw_data={}
        ),
        KalshiMarket(
            ticker="SOCCERLALIGA-25DEC-BAR",
            title="Barcelona will defeat Real Madrid in La Liga match",
            subtitle="El Clasico",
            category="SPORTS", 
            status="open",
            yes_ask=0.65,
            yes_bid=0.61,
            no_ask=0.39,
            no_bid=0.35,
            open_time=datetime(2024, 12, 22, tzinfo=timezone.utc),
            close_time=datetime(2024, 12, 25, 18, 0, tzinfo=timezone.utc),
            settle_time=datetime(2024, 12, 25, 20, 0, tzinfo=timezone.utc),
            raw_data={}
        ),
        KalshiMarket(
            ticker="SOCCERBUND-26DEC-BAY",
            title="Bayern Munich vs Borussia Dortmund ends in draw",
            subtitle="Bundesliga",
            category="SPORTS",
            status="open", 
            yes_ask=0.35,
            yes_bid=0.31,
            no_ask=0.69,
            no_bid=0.65,
            open_time=datetime(2024, 12, 23, tzinfo=timezone.utc),
            close_time=datetime(2024, 12, 26, 14, 0, tzinfo=timezone.utc),
            settle_time=datetime(2024, 12, 26, 16, 0, tzinfo=timezone.utc),
            raw_data={}
        )
    ]
    
    # Sample Polymarket markets
    polymarket_markets = [
        PolymarketMarket(
            condition_id="0x123abc",
            market_slug="arsenal-beats-chelsea-dec-24",
            question="Will Arsenal beat Chelsea in their Premier League match on December 24th?",
            description="Premier League match between Arsenal and Chelsea at Emirates Stadium",
            category="Sports",
            end_date_iso=datetime(2024, 12, 24, 17, 0, tzinfo=timezone.utc),
            outcomes=["Yes", "No"],
            outcome_prices=[0.51, 0.49],
            tokens=[
                PolymarketToken(token_id="token123", outcome="Yes", price=0.51, win_index=0),
                PolymarketToken(token_id="token456", outcome="No", price=0.49, win_index=1)
            ],
            raw_data={}
        ),
        PolymarketMarket(
            condition_id="0x456def",
            market_slug="el-clasico-barca-wins",
            question="Will Barcelona defeat Real Madrid in El Clasico?",
            description="La Liga match between Barcelona and Real Madrid",
            category="Sports",
            end_date_iso=datetime(2024, 12, 25, 20, 0, tzinfo=timezone.utc),
            outcomes=["Yes", "No"],
            outcome_prices=[0.63, 0.37],
            tokens=[
                PolymarketToken(token_id="token789", outcome="Yes", price=0.63, win_index=0),
                PolymarketToken(token_id="token012", outcome="No", price=0.37, win_index=1)
            ],
            raw_data={}
        ),
        PolymarketMarket(
            condition_id="0x789ghi",
            market_slug="bayern-dortmund-draw",
            question="Will Bayern Munich vs Borussia Dortmund end in a draw?",
            description="Bundesliga match at Allianz Arena",
            category="Sports",
            end_date_iso=datetime(2024, 12, 26, 16, 0, tzinfo=timezone.utc),
            outcomes=["Yes", "No"],
            outcome_prices=[0.33, 0.67],
            tokens=[
                PolymarketToken(token_id="token345", outcome="Yes", price=0.33, win_index=0),
                PolymarketToken(token_id="token678", outcome="No", price=0.67, win_index=1)
            ],
            raw_data={}
        ),
        PolymarketMarket(
            condition_id="0xabcdef",
            market_slug="manchester-city-liverpool",
            question="Will Manchester City beat Liverpool?",
            description="Premier League match",
            category="Sports",
            end_date_iso=datetime(2024, 12, 27, 17, 0, tzinfo=timezone.utc),
            outcomes=["Yes", "No"],
            outcome_prices=[0.45, 0.55],
            tokens=[
                PolymarketToken(token_id="token901", outcome="Yes", price=0.45, win_index=0),
                PolymarketToken(token_id="token234", outcome="No", price=0.55, win_index=1)
            ],
            raw_data={}
        )
    ]
    
    return kalshi_markets, polymarket_markets


def main():
    """Test market matching with sample data."""
    logger.info("Testing market discovery and matching with sample data")
    
    # Create sample markets
    kalshi_markets, polymarket_markets = create_sample_markets()
    
    logger.info(f"Created {len(kalshi_markets)} sample Kalshi markets")
    logger.info(f"Created {len(polymarket_markets)} sample Polymarket markets")
    
    # Test market matching
    matcher = MarketMatcher(min_confidence_threshold=0.6)
    matched_markets = matcher.find_matches(kalshi_markets, polymarket_markets)
    
    logger.info(f"Found {len(matched_markets)} matched markets")
    
    # Display results
    logger.info("\n" + "="*50)
    logger.info("MARKET MATCHING RESULTS")
    logger.info("="*50)
    
    for i, match in enumerate(matched_markets, 1):
        logger.info(f"\nMatch {i}:")
        logger.info(f"  Confidence: {match.match_confidence:.3f}")
        logger.info(f"  Kalshi: {match.kalshi_market.ticker}")
        logger.info(f"    Title: {match.kalshi_market.title}")
        logger.info(f"  Polymarket: {match.polymarket_market.market_slug}")
        logger.info(f"    Question: {match.polymarket_market.question}")
        logger.info(f"  Reason: {match.match_reason}")
        logger.info(f"  Settlement: {match.settlement_notes}")
        logger.info(f"  Rules Hash: {matcher.generate_rules_hash(match)[:16]}...")
    
    # Test configuration generation
    if matched_markets:
        logger.info("\nGenerating configuration files...")
        
        config_generator = ConfigGenerator(env="demo")
        output_dir = Path(__file__).parent.parent / "config"
        
        # Generate markets config
        markets_config_path = output_dir / "markets_soccer.yaml" 
        config_generator.generate_config(matched_markets, markets_config_path)
        
        # Generate params config
        params_config_path = output_dir / "params_demo.yaml"
        config_generator.generate_params_file(params_config_path, "demo")
        
        logger.info(f"Configuration files generated:")
        logger.info(f"  - Markets: {markets_config_path}")
        logger.info(f"  - Parameters: {params_config_path}")
    
    logger.info("\nTest completed successfully!")


if __name__ == "__main__":
    main()