"""Configuration generator for matched markets."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from src.core.market_matcher import MarketMatcher
from src.models.types import MatchedMarket

logger = logging.getLogger(__name__)


class ConfigGenerator:
    """Generates YAML configuration from matched markets."""
    
    def __init__(self, env: str = "demo"):
        """Initialize the generator.
        
        Args:
            env: Environment (demo or prod)
        """
        self.env = env
        self.matcher = MarketMatcher()
    
    def generate_config(
        self,
        matched_markets: list[MatchedMarket],
        output_path: str | Path
    ) -> None:
        """Generate markets_soccer.yaml configuration.
        
        Args:
            matched_markets: List of matched markets
            output_path: Path to write configuration file
        """
        logger.info(f"Generating configuration for {len(matched_markets)} matched markets")
        
        # Build configuration structure
        config_data = {
            "env": self.env,
            "markets": [],
            "params_file": f"params_{self.env}.yaml"
        }
        
        for i, match in enumerate(matched_markets):
            market_config = self._create_market_config(match, i + 1)
            config_data["markets"].append(market_config)
        
        # Write to file
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            yaml.dump(
                config_data,
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
                width=120
            )
        
        logger.info(f"Configuration written to {output_path}")
    
    def _create_market_config(self, match: MatchedMarket, market_id: int) -> dict[str, Any]:
        """Create market configuration from matched market."""
        kalshi_market = match.kalshi_market
        poly_market = match.polymarket_market
        
        # Determine market archetype
        archetype = "two_outcome"
        if len(poly_market.outcomes) == 3:
            archetype = "three_outcome"
        
        # Build token IDs mapping
        token_ids = {}
        for token in poly_market.tokens:
            outcome_key = self._map_outcome_to_key(token.outcome, archetype)
            if outcome_key:
                token_ids[outcome_key] = token.token_id
        
        # Generate market ID
        safe_title = self._sanitize_string(kalshi_market.title)
        market_config_id = f"soccer_{market_id:03d}_{safe_title[:20]}"
        
        # Create configuration
        config = {
            "id": market_config_id,
            "league": self._infer_league(kalshi_market, poly_market),
            "match_name": self._create_match_name(kalshi_market, poly_market),
            "start_time_utc": self._format_datetime(kalshi_market.open_time),
            "scheduled_end_time_utc": self._format_datetime(
                kalshi_market.close_time or kalshi_market.settle_time
            ),
            "kalshi": {
                "env": self.env,
                "ticker": kalshi_market.ticker,
                "market_id": None,  # To be filled later
                "yes_side_definition": kalshi_market.title
            },
            "polymarket": {
                "market_slug": poly_market.market_slug,
                "token_ids": token_ids,
                "outcome_definition": poly_market.question
            },
            "settlement_equivalence": {
                "rules_hash": self.matcher.generate_rules_hash(match),
                "notes": match.settlement_notes
            },
            "archetype": archetype
        }
        
        # Add confidence as comment in YAML
        config["_match_confidence"] = round(match.match_confidence, 3)
        config["_match_reason"] = match.match_reason
        
        return config
    
    def _map_outcome_to_key(self, outcome: str, archetype: str) -> str | None:
        """Map outcome text to standardized key."""
        outcome_lower = outcome.lower()
        
        if archetype == "two_outcome":
            # For YES/NO markets, we typically use "yes" and "no"
            if any(word in outcome_lower for word in ["yes", "win", "true", "occurs"]):
                return "yes"
            elif any(word in outcome_lower for word in ["no", "lose", "false", "not occur"]):
                return "no"
            else:
                # Default to yes for positive outcomes
                return "yes"
        
        elif archetype == "three_outcome":
            # For Home/Draw/Away markets
            if any(word in outcome_lower for word in ["home", "team 1", "first"]):
                return "home"
            elif any(word in outcome_lower for word in ["draw", "tie", "tied"]):
                return "draw"
            elif any(word in outcome_lower for word in ["away", "team 2", "second"]):
                return "away"
            else:
                # Try to infer from position
                return "home"  # Default
        
        return None
    
    def _infer_league(self, kalshi_market, poly_market) -> str:
        """Infer league from market text."""
        text = f"{kalshi_market.title} {kalshi_market.subtitle or ''} {poly_market.question}".lower()
        
        league_mappings = {
            "EPL": ["premier league", "epl", "english premier"],
            "Bundesliga": ["bundesliga", "german"],
            "La Liga": ["la liga", "spanish", "spain"],
            "Serie A": ["serie a", "italian", "italy"],
            "Ligue 1": ["ligue 1", "french", "france"]
        }
        
        for league, keywords in league_mappings.items():
            if any(keyword in text for keyword in keywords):
                return league
        
        return "EPL"  # Default
    
    def _create_match_name(self, kalshi_market, poly_market) -> str:
        """Create descriptive match name."""
        # Try to extract team names
        kalshi_text = f"{kalshi_market.title} {kalshi_market.subtitle or ''}".strip()
        
        # Look for vs pattern
        import re
        vs_match = re.search(r'([A-Za-z\s]+)\s+(?:vs?\.?|v\.?|-)\s+([A-Za-z\s]+)', kalshi_text)
        if vs_match:
            team1 = vs_match.group(1).strip()
            team2 = vs_match.group(2).strip()
            return f"{team1} vs {team2}"
        
        # Fallback to first part of title
        return kalshi_text.split(' - ')[0].split(' vs ')[0].strip()
    
    def _format_datetime(self, dt: datetime | None) -> str:
        """Format datetime for YAML."""
        if not dt:
            return "2024-01-01T00:00:00Z"  # Placeholder
        
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    def _sanitize_string(self, s: str) -> str:
        """Sanitize string for use in IDs."""
        import re
        # Remove special characters, keep alphanumeric and spaces
        sanitized = re.sub(r'[^a-zA-Z0-9\s]', '', s)
        # Replace spaces with underscores
        sanitized = re.sub(r'\s+', '_', sanitized)
        # Convert to lowercase
        return sanitized.lower()
    
    def generate_params_file(
        self,
        output_path: str | Path,
        env: str | None = None
    ) -> None:
        """Generate parameters file for the environment.
        
        Args:
            output_path: Path to write parameters file
            env: Environment (defaults to self.env)
        """
        env = env or self.env
        
        # Default parameters based on spec
        if env == "demo":
            params = {
                # Fair price model
                "w_poly_base_prematch": 0.70,
                "w_poly_base_inplay": 0.85,
                "poly_spread_narrow_threshold": 0.02,
                "poly_spread_wide_threshold": 0.06,
                "poly_spread_narrow_bonus": 0.05,
                "poly_spread_wide_penalty": 0.10,
                "shock_score_threshold": 3.0,
                "pause_seconds_shock": 10,
                
                # Quoting
                "base_half_spread_prematch": 0.03,
                "base_half_spread_inplay": 0.06,
                "adv_buffer_prematch": 0.01,
                "adv_buffer_inplay": 0.03,
                "adv_buffer_shock": 0.02,
                "repricing_tick_threshold_prematch": 0.02,
                "repricing_tick_threshold_inplay": 0.01,
                "min_seconds_between_writes_prematch": 0.5,
                "min_seconds_between_writes_inplay": 0.2,
                
                # Order sizing - DEMO values
                "max_order_notional_demo": 3.00,
                "max_order_notional_live": 3.00,  # Use demo values
                "max_contracts_per_order_demo": 25,
                "max_contracts_per_order_live": 25,  # Use demo values
                "max_size_vs_depth_ratio": 0.25,
                
                # Risk limits - DEMO values
                "max_position_notional_demo": 25.00,
                "max_position_notional_live": 25.00,  # Use demo values
                "max_total_notional_demo": 125.00,
                "max_total_notional_live": 125.00,  # Use demo values
                "max_filled_notional_per_minute_demo": 20.00,
                "max_filled_notional_per_minute_live": 20.00,  # Use demo values
                "drawdown_limit_demo": 50.00,
                "drawdown_limit_live": 50.00,  # Use demo values
                
                # Match phase
                "stop_before_end_seconds": 600,  # 10 minutes
                
                # Data freshness
                "stale_seconds_prematch": 10,
                "stale_seconds_inplay": 3,
                "warmup_seconds": 5,
                
                # Polymarket polling
                "poll_interval_prematch_ms": 2000,
                "poll_interval_inplay_ms": 500,
                "poll_interval_cooldown_ms": 250,
                "cooldown_duration_seconds": 10,
            }
        else:
            # Production parameters
            params = {
                # Fair price model
                "w_poly_base_prematch": 0.70,
                "w_poly_base_inplay": 0.85,
                "poly_spread_narrow_threshold": 0.02,
                "poly_spread_wide_threshold": 0.06,
                "poly_spread_narrow_bonus": 0.05,
                "poly_spread_wide_penalty": 0.10,
                "shock_score_threshold": 3.0,
                "pause_seconds_shock": 10,
                
                # Quoting
                "base_half_spread_prematch": 0.03,
                "base_half_spread_inplay": 0.06,
                "adv_buffer_prematch": 0.01,
                "adv_buffer_inplay": 0.03,
                "adv_buffer_shock": 0.02,
                "repricing_tick_threshold_prematch": 0.02,
                "repricing_tick_threshold_inplay": 0.01,
                "min_seconds_between_writes_prematch": 0.5,
                "min_seconds_between_writes_inplay": 0.2,
                
                # Order sizing - LIVE values
                "max_order_notional_demo": 1.00,  # Not used in prod
                "max_order_notional_live": 1.00,
                "max_contracts_per_order_demo": 10,  # Not used in prod
                "max_contracts_per_order_live": 10,
                "max_size_vs_depth_ratio": 0.25,
                
                # Risk limits - LIVE values
                "max_position_notional_demo": 10.00,  # Not used in prod
                "max_position_notional_live": 10.00,
                "max_total_notional_demo": 50.00,  # Not used in prod
                "max_total_notional_live": 50.00,
                "max_filled_notional_per_minute_demo": 8.00,  # Not used in prod
                "max_filled_notional_per_minute_live": 8.00,
                "drawdown_limit_demo": 20.00,  # Not used in prod
                "drawdown_limit_live": 20.00,
                
                # Match phase
                "stop_before_end_seconds": 600,  # 10 minutes
                
                # Data freshness
                "stale_seconds_prematch": 10,
                "stale_seconds_inplay": 3,
                "warmup_seconds": 5,
                
                # Polymarket polling
                "poll_interval_prematch_ms": 2000,
                "poll_interval_inplay_ms": 500,
                "poll_interval_cooldown_ms": 250,
                "cooldown_duration_seconds": 10,
            }
        
        # Write to file
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            yaml.dump(
                params,
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True
            )
        
        logger.info(f"Parameters written to {output_path}")