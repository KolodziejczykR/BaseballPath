"""
Baseball Rankings Integration Utilities
Helper functions to integrate Massey rankings data with the school filtering system
"""

import os
import sys
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import name resolver
from backend.database.name_matching import get_resolver

load_dotenv()

logger = logging.getLogger(__name__)

class BaseballRankingsIntegration:
    """Integration class for baseball rankings data with school filtering"""

    def __init__(self):
        """Initialize Supabase client and name resolver"""
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")

        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")

        self.supabase: Client = create_client(url, key)
        self.rankings_table = "baseball_rankings_data"
        self.schools_table = "school_data_general"

        # Initialize name resolver for school_name <-> team_name mapping
        self.name_resolver = get_resolver()

    def get_school_strength_profile(self, school_name: str, years: List[int] = None) -> Dict:
        """
        Get strength profile for a school across multiple years

        Args:
            school_name: Name of the school (from school_data_general format: "University, City, ST")
            years: List of years to include (defaults to [2023, 2024, 2025])

        Returns:
            Dictionary with strength metrics and trends
        """
        if years is None:
            years = [2023, 2024, 2025]

        try:
            # Resolve school_name to team_name
            team_name = self.name_resolver.get_team_name(school_name, verified_only=False)

            if not team_name:
                logger.debug(f"No baseball rankings mapping found for: {school_name}")
                return {
                    "school_name": school_name,
                    "has_data": False,
                    "message": "No baseball rankings mapping found for this school"
                }

            # Query rankings data for the school using team_name
            response = self.supabase.table(self.rankings_table)\
                .select("*")\
                .eq("team_name", team_name)\
                .in_("year", years)\
                .order("year", desc=True)\
                .execute()

            if not response.data:
                return {
                    "school_name": school_name,
                    "team_name": team_name,
                    "has_data": False,
                    "message": "No rankings data found for this team"
                }

            rankings_data = response.data

            # Calculate aggregate metrics
            recent_data = rankings_data[0] if rankings_data else None
            all_years_data = {year: None for year in years}

            for record in rankings_data:
                all_years_data[record['year']] = record

            # Calculate 3-year weighted average (50%, 30%, 20% for most recent to oldest)
            weights = [0.5, 0.3, 0.2]
            weighted_metrics = self._calculate_weighted_averages(rankings_data, weights)

            # Determine trend
            trend = self._calculate_trend(rankings_data)

            # Calculate percentile within division (if multiple years available)
            division_percentile = self._get_division_percentile(
                recent_data['overall_rating'],
                recent_data['year'],
                recent_data['division']
            ) if recent_data else None

            return {
                "school_name": school_name,
                "team_name": team_name,
                "has_data": True,
                "current_division": recent_data['division'] if recent_data else None,
                "most_recent_year": recent_data['year'] if recent_data else None,
                "division_group": recent_data.get('division_group') if recent_data else None,
                "division_percentile": division_percentile,
                "offensive_rating": (
                    weighted_metrics.get('weighted_offensive_rating')
                    if weighted_metrics
                    else (recent_data.get('offensive_rating') if recent_data else None)
                ),
                "defensive_rating": (
                    weighted_metrics.get('weighted_defensive_rating')
                    if weighted_metrics
                    else (recent_data.get('defensive_rating') if recent_data else None)
                ),

                # Current season metrics
                "current_season": {
                    "year": recent_data['year'],
                    "record": recent_data['record'],
                    "overall_rating": recent_data['overall_rating'],
                    "power_rating": recent_data['power_rating'],
                    "offensive_rating": recent_data.get('offensive_rating'),
                    "defensive_rating": recent_data.get('defensive_rating'),
                    "win_percentage": recent_data['win_percentage'],
                    "division_percentile": division_percentile,
                    "division_group": recent_data.get('division_group'),
                } if recent_data else None,

                # Multi-year analysis
                "weighted_averages": weighted_metrics,
                "trend_analysis": trend,
                "years_with_data": [r['year'] for r in rankings_data],
                "historical_data": all_years_data,

                # Strength classification
                "strength_classification": self._classify_strength(weighted_metrics, division_percentile),
                "playing_time_factor": self._calculate_playing_time_factor(weighted_metrics, division_percentile)
            }

        except Exception as e:
            logger.error(f"Error getting strength profile for {school_name}: {e}")
            return {
                "school_name": school_name,
                "has_data": False,
                "error": str(e)
            }

    def _calculate_weighted_averages(self, rankings_data: List[Dict], weights: List[float]) -> Dict:
        """Calculate weighted averages for multiple metrics"""
        if not rankings_data:
            return {}

        # Sort by year descending (most recent first)
        sorted_data = sorted(rankings_data, key=lambda x: x['year'], reverse=True)

        metrics = ['overall_rating', 'power_rating', 'offensive_rating', 'defensive_rating', 'win_percentage']
        weighted_averages = {}

        for metric in metrics:
            total_weighted_value = 0
            total_weight = 0

            for i, record in enumerate(sorted_data):
                if i >= len(weights):
                    break

                value = record.get(metric)
                if value is not None:
                    total_weighted_value += value * weights[i]
                    total_weight += weights[i]

            if total_weight > 0:
                weighted_averages[f"weighted_{metric}"] = round(total_weighted_value / total_weight, 3)

        return weighted_averages

    def _calculate_trend(self, rankings_data: List[Dict]) -> Dict:
        """
        Calculate trend direction based on overall rating changes

        Note: Massey ratings use LOWER = BETTER
        - Negative change = improving (rating decreased/got better)
        - Positive change = declining (rating increased/got worse)
        """
        if len(rankings_data) < 2:
            return {"trend": "insufficient_data", "change": None}

        # Sort by year ascending
        sorted_data = sorted(rankings_data, key=lambda x: x['year'])

        # Compare first and last available years
        first_rating = sorted_data[0].get('overall_rating')
        last_rating = sorted_data[-1].get('overall_rating')

        if first_rating is None or last_rating is None:
            return {"trend": "insufficient_data", "change": None}

        change = last_rating - first_rating

        # Lower rating = better, so negative change = improving
        if change < -2.0:
            trend = "improving"  # Rating decreased (got better)
        elif change > 2.0:
            trend = "declining"  # Rating increased (got worse)
        else:
            trend = "stable"

        return {
            "trend": trend,
            "change": round(change, 2),
            "rating_change": round(change, 2),
            "years_span": f"{sorted_data[0]['year']}-{sorted_data[-1]['year']}"
        }

    def _get_division_percentile(self, overall_rating: float, year: int, division: int) -> Optional[float]:
        """
        Get percentile ranking within division for a given year

        Note: Massey ratings use LOWER = BETTER (e.g., 1.0 = #1 team, 300.0 = #300 team)
        Percentile returned is standard (higher = better), where 100th percentile = best team
        """
        try:
            response = self.supabase.table(self.rankings_table)\
                .select("overall_rating")\
                .eq("year", year)\
                .eq("division", division)\
                .not_.is_("overall_rating", "null")\
                .execute()

            if not response.data:
                return None

            ratings = [r['overall_rating'] for r in response.data]
            ratings.sort()

            # Find percentile (count teams with HIGHER/WORSE ratings)
            # Lower Massey rating = better team, so we count teams with higher ratings
            position = sum(1 for r in ratings if r > overall_rating)
            percentile = (position / len(ratings)) * 100

            return round(percentile, 1)

        except Exception as e:
            logger.error(f"Error calculating percentile: {e}")
            return None

    def _classify_strength(self, weighted_metrics: Dict, division_percentile: Optional[float]) -> str:
        """Classify school strength based on metrics"""
        if not weighted_metrics or division_percentile is None:
            return "unknown"

        if division_percentile >= 90:
            return "elite"
        elif division_percentile >= 75:
            return "strong"
        elif division_percentile >= 50:
            return "competitive"
        elif division_percentile >= 25:
            return "developing"
        else:
            return "rebuilding"

    def _calculate_playing_time_factor(self, weighted_metrics: Dict, division_percentile: Optional[float]) -> float:
        """
        Calculate playing time opportunity factor
        Higher rating = more competitive = lower opportunity factor
        """
        if division_percentile is None:
            return 1.0  # Neutral factor

        # Scale from 0.7 (elite programs, harder to play) to 1.3 (rebuilding programs, more opportunities)
        if division_percentile >= 90:
            return 0.7  # Elite programs - very competitive
        elif division_percentile >= 75:
            return 0.8  # Strong programs - competitive
        elif division_percentile >= 50:
            return 1.0  # Average programs - normal opportunities
        elif division_percentile >= 25:
            return 1.2  # Developing programs - more opportunities
        else:
            return 1.3  # Rebuilding programs - most opportunities

    def get_division_rankings(self, year: int, division: int, limit: int = 50) -> List[Dict]:
        """
        Get top rankings for a specific year and division

        Note: Massey ratings use LOWER = BETTER, so we order ASC to get best teams
        """
        try:
            response = self.supabase.table(self.rankings_table)\
                .select("*")\
                .eq("year", year)\
                .eq("division", division)\
                .order("overall_rating", desc=False)\
                .limit(limit)\
                .execute()

            return response.data if response.data else []

        except Exception as e:
            logger.error(f"Error getting division rankings: {e}")
            return []

    def compare_schools_strength(self, school_names: List[str]) -> Dict:
        """Compare strength metrics between multiple schools"""
        try:
            school_profiles = {}
            for school_name in school_names:
                school_profiles[school_name] = self.get_school_strength_profile(school_name)

            # Create comparison summary
            comparison = {
                "schools": school_profiles,
                "comparison_summary": {
                    "strongest_program": None,
                    "most_improving": None,
                    "best_playing_time_opportunity": None
                }
            }

            # Find strongest program (lowest weighted overall rating = best)
            strongest_rating = 9999  # Initialize high to find minimum
            strongest_school = None

            # Find most improving program (most negative change = best improvement)
            best_trend = 9999  # Initialize high to find most negative
            most_improving_school = None

            # Find best playing time opportunity (highest factor)
            best_opportunity = 0
            best_opportunity_school = None

            for school_name, profile in school_profiles.items():
                if not profile.get('has_data'):
                    continue

                # Check strongest (lower rating = better)
                weighted_overall = profile.get('weighted_averages', {}).get('weighted_overall_rating')
                if weighted_overall and weighted_overall < strongest_rating:
                    strongest_rating = weighted_overall
                    strongest_school = school_name

                # Check most improving (most negative change = best)
                trend_change = profile.get('trend_analysis', {}).get('change')
                if trend_change is not None and trend_change < best_trend:
                    best_trend = trend_change
                    most_improving_school = school_name

                # Check best opportunity
                playing_time_factor = profile.get('playing_time_factor', 1.0)
                if playing_time_factor > best_opportunity:
                    best_opportunity = playing_time_factor
                    best_opportunity_school = school_name

            comparison["comparison_summary"] = {
                "strongest_program": strongest_school,
                "most_improving": most_improving_school,
                "best_playing_time_opportunity": best_opportunity_school
            }

            return comparison

        except Exception as e:
            logger.error(f"Error comparing schools: {e}")
            return {"error": str(e)}

def main():
    """Example usage of the integration class"""
    try:
        integration = BaseballRankingsIntegration()

        # Example 1: Get strength profile for a school
        print("=== School Strength Profile ===")
        profile = integration.get_school_strength_profile("Stanford")
        print(f"Stanford profile: {profile}")

        # Example 2: Compare multiple schools
        print("\n=== School Comparison ===")
        schools_to_compare = ["Stanford", "UCLA", "Texas"]
        comparison = integration.compare_schools_strength(schools_to_compare)
        print(f"Comparison: {comparison}")

        # Example 3: Get division rankings
        print("\n=== Division Rankings ===")
        rankings = integration.get_division_rankings(2024, 1, limit=10)
        print(f"Top 10 D1 teams in 2024: {[r['team_name'] for r in rankings]}")

    except Exception as e:
        logger.error(f"Error in main: {e}")

if __name__ == "__main__":
    main()
