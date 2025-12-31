"""Market matching algorithm to find identical markets between Kalshi and Polymarket."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Any

from src.models.types import KalshiMarket, PolymarketMarket, MatchedMarket

logger = logging.getLogger(__name__)


class MarketMatcher:
    """Matches markets between Kalshi and Polymarket."""
    
    def __init__(
        self,
        min_confidence_threshold: float = 0.7,
        max_time_diff_hours: int = 24,
        whitelisted_leagues: list[str] | None = None
    ):
        """Initialize the matcher.
        
        Args:
            min_confidence_threshold: Minimum confidence score for matches
            max_time_diff_hours: Maximum time difference between market end times
            whitelisted_leagues: List of whitelisted leagues (EPL, Bundesliga, etc.)
        """
        self.min_confidence_threshold = min_confidence_threshold
        self.max_time_diff_hours = max_time_diff_hours
        self.whitelisted_leagues = whitelisted_leagues or [
            "EPL", "Premier League", "English Premier League",
            "Bundesliga", "German Bundesliga", 
            "La Liga", "Spanish La Liga",
            "Serie A", "Italian Serie A",
            "Ligue 1", "French Ligue 1"
        ]
        
        # Team name normalization mappings
        self.team_aliases = {
            "man city": ["manchester city", "mcfc"],
            "man united": ["manchester united", "mufc"],
            "tottenham": ["spurs", "thfc"],
            "newcastle": ["newcastle united", "nufc"],
            "west ham": ["west ham united"],
            "real madrid": ["real", "madrid"],
            "barcelona": ["barca", "fc barcelona"],
            "atletico madrid": ["atletico"],
            "inter milan": ["inter", "internazionale"],
            "ac milan": ["milan", "ac milan"],
            "psg": ["paris saint-germain", "paris saint germain"],
            "bayern munich": ["bayern", "fc bayern"],
            "borussia dortmund": ["dortmund", "bvb"],
        }
    
    def find_matches(
        self,
        kalshi_markets: list[KalshiMarket],
        polymarket_markets: list[PolymarketMarket]
    ) -> list[MatchedMarket]:
        """Find matching markets between the two platforms.
        
        Args:
            kalshi_markets: List of Kalshi markets
            polymarket_markets: List of Polymarket markets
            
        Returns:
            List of matched markets
        """
        matches = []
        
        logger.info(f"Matching {len(kalshi_markets)} Kalshi markets with {len(polymarket_markets)} Polymarket markets")
        
        for kalshi_market in kalshi_markets:
            best_match = None
            best_confidence = 0.0
            
            for polymarket_market in polymarket_markets:
                confidence = self._calculate_match_confidence(kalshi_market, polymarket_market)
                
                if confidence > best_confidence and confidence >= self.min_confidence_threshold:
                    best_confidence = confidence
                    best_match = polymarket_market
            
            if best_match:
                match_reason = self._generate_match_reason(kalshi_market, best_match, best_confidence)
                settlement_notes = self._generate_settlement_notes(kalshi_market, best_match)
                
                matched_market = MatchedMarket(
                    kalshi_market=kalshi_market,
                    polymarket_market=best_match,
                    match_confidence=best_confidence,
                    match_reason=match_reason,
                    settlement_notes=settlement_notes
                )
                
                matches.append(matched_market)
                
                logger.info(f"Matched: {kalshi_market.ticker} <-> {best_match.question} (confidence: {best_confidence:.2f})")
        
        logger.info(f"Found {len(matches)} market matches")
        return matches
    
    def _calculate_match_confidence(
        self,
        kalshi_market: KalshiMarket,
        poly_market: PolymarketMarket
    ) -> float:
        """Calculate match confidence between two markets.
        
        Args:
            kalshi_market: Kalshi market
            poly_market: Polymarket market
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Extract match components
        kalshi_text = f"{kalshi_market.title} {kalshi_market.subtitle or ''}".strip().lower()
        poly_text = poly_market.question.lower()
        
        # Extract teams/entities
        kalshi_teams = self._extract_teams(kalshi_text)
        poly_teams = self._extract_teams(poly_text)
        
        # Extract match type (win, draw, etc.)
        kalshi_type = self._extract_match_type(kalshi_text)
        poly_type = self._extract_match_type(poly_text)
        
        # Calculate component similarities
        text_similarity = self._text_similarity(kalshi_text, poly_text)
        team_similarity = self._team_similarity(kalshi_teams, poly_teams)
        type_similarity = 1.0 if kalshi_type == poly_type else 0.0
        time_similarity = self._time_similarity(kalshi_market, poly_market)
        league_similarity = self._league_similarity(kalshi_text, poly_text)
        
        # Weighted average
        weights = {
            "text": 0.3,
            "teams": 0.4,
            "type": 0.1,
            "time": 0.1,
            "league": 0.1
        }
        
        confidence = (
            weights["text"] * text_similarity +
            weights["teams"] * team_similarity +
            weights["type"] * type_similarity +
            weights["time"] * time_similarity +
            weights["league"] * league_similarity
        )
        
        return min(1.0, max(0.0, confidence))
    
    def _extract_teams(self, text: str) -> set[str]:
        """Extract team names from market text."""
        teams = set()
        
        # Common patterns for team extraction
        patterns = [
            r"([a-z\s]+) vs ([a-z\s]+)",
            r"([a-z\s]+) v ([a-z\s]+)",
            r"([a-z\s]+) - ([a-z\s]+)",
            r"([a-z\s]+) will (?:beat|defeat) ([a-z\s]+)",
            r"will ([a-z\s]+) (?:beat|defeat) ([a-z\s]+)",
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                team1 = match.group(1).strip()
                team2 = match.group(2).strip()
                
                # Normalize team names
                team1 = self._normalize_team_name(team1)
                team2 = self._normalize_team_name(team2)
                
                if team1:
                    teams.add(team1)
                if team2:
                    teams.add(team2)
        
        return teams
    
    def _extract_match_type(self, text: str) -> str:
        """Extract match type from text (win, draw, etc.)."""
        if any(word in text for word in ["win", "beat", "defeat", "victory"]):
            return "win"
        elif any(word in text for word in ["draw", "tie", "tied"]):
            return "draw"
        elif any(word in text for word in ["lose", "loss"]):
            return "loss"
        elif any(word in text for word in ["score", "goal"]):
            return "score"
        else:
            return "unknown"
    
    def _normalize_team_name(self, team_name: str) -> str:
        """Normalize team name using aliases."""
        team_name = team_name.strip().lower()
        
        # Check aliases
        for canonical, aliases in self.team_aliases.items():
            if team_name == canonical or team_name in aliases:
                return canonical
        
        # Remove common suffixes
        suffixes = ["fc", "united", "city"]
        for suffix in suffixes:
            if team_name.endswith(f" {suffix}"):
                team_name = team_name[:-len(suffix)-1]
        
        return team_name
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using sequence matching."""
        return SequenceMatcher(None, text1, text2).ratio()
    
    def _team_similarity(self, teams1: set[str], teams2: set[str]) -> float:
        """Calculate similarity between team sets."""
        if not teams1 or not teams2:
            return 0.0
        
        intersection = teams1.intersection(teams2)
        union = teams1.union(teams2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _time_similarity(self, kalshi_market: KalshiMarket, poly_market: PolymarketMarket) -> float:
        """Calculate time similarity between markets."""
        kalshi_time = kalshi_market.close_time or kalshi_market.settle_time
        poly_time = poly_market.end_date_iso
        
        if not kalshi_time or not poly_time:
            return 0.5  # Neutral if we can't compare
        
        time_diff = abs((kalshi_time - poly_time).total_seconds())
        max_diff = self.max_time_diff_hours * 3600
        
        if time_diff <= max_diff:
            return 1.0 - (time_diff / max_diff)
        else:
            return 0.0
    
    def _league_similarity(self, kalshi_text: str, poly_text: str) -> float:
        """Check if both markets are from whitelisted leagues."""
        kalshi_league = None
        poly_league = None
        
        for league in self.whitelisted_leagues:
            if league.lower() in kalshi_text:
                kalshi_league = league
            if league.lower() in poly_text:
                poly_league = league
        
        if kalshi_league and poly_league:
            return 1.0 if kalshi_league == poly_league else 0.5
        elif kalshi_league or poly_league:
            return 0.5
        else:
            return 0.0  # No league info
    
    def _generate_match_reason(
        self,
        kalshi_market: KalshiMarket,
        poly_market: PolymarketMarket,
        confidence: float
    ) -> str:
        """Generate human-readable match reason."""
        kalshi_teams = self._extract_teams(f"{kalshi_market.title} {kalshi_market.subtitle or ''}".lower())
        poly_teams = self._extract_teams(poly_market.question.lower())
        
        common_teams = kalshi_teams.intersection(poly_teams)
        
        reasons = []
        
        if common_teams:
            reasons.append(f"Common teams: {', '.join(common_teams)}")
        
        if confidence > 0.9:
            reasons.append("Very high text similarity")
        elif confidence > 0.8:
            reasons.append("High text similarity")
        
        kalshi_type = self._extract_match_type(f"{kalshi_market.title} {kalshi_market.subtitle or ''}".lower())
        poly_type = self._extract_match_type(poly_market.question.lower())
        
        if kalshi_type == poly_type and kalshi_type != "unknown":
            reasons.append(f"Same market type: {kalshi_type}")
        
        return "; ".join(reasons) if reasons else "General similarity match"
    
    def _generate_settlement_notes(
        self,
        kalshi_market: KalshiMarket,
        poly_market: PolymarketMarket
    ) -> str:
        """Generate settlement equivalence notes."""
        notes = []
        
        # Check outcome structure
        if len(poly_market.outcomes) == 2:
            notes.append("Two-outcome market (YES/NO)")
        elif len(poly_market.outcomes) == 3:
            notes.append("Three-outcome market (Home/Draw/Away)")
        else:
            notes.append(f"{len(poly_market.outcomes)}-outcome market")
        
        # Add timing notes
        if kalshi_market.close_time and poly_market.end_date_iso:
            time_diff = abs((kalshi_market.close_time - poly_market.end_date_iso).total_seconds()) / 3600
            if time_diff < 1:
                notes.append("Close times align within 1 hour")
            else:
                notes.append(f"Close times differ by {time_diff:.1f} hours")
        
        return "; ".join(notes)
    
    def generate_rules_hash(self, matched_market: MatchedMarket) -> str:
        """Generate SHA256 hash of settlement rules for validation."""
        # Normalize settlement text
        kalshi_text = f"{matched_market.kalshi_market.title} {matched_market.kalshi_market.subtitle or ''}".strip()
        poly_text = matched_market.polymarket_market.question.strip()
        
        # Create normalized settlement text
        settlement_text = f"KALSHI: {kalshi_text}\nPOLY: {poly_text}"
        settlement_text = re.sub(r'\s+', ' ', settlement_text).strip().lower()
        
        # Generate hash
        return hashlib.sha256(settlement_text.encode()).hexdigest()