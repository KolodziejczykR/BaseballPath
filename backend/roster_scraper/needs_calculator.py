"""
Position needs calculator for BaseballPath
Computes per-position recruiting need scores (0.0–1.0) from roster data.

Algorithm per position:
  need_score = (departure_factor × 0.50) + (depth_factor × 0.30) + (youth_factor × 0.20)

  departure_factor: seniors_at_position / total_at_position
  depth_factor:     max(0, 1.0 - (current_count / ideal_count))
  youth_factor:     weighted avg class year (older = higher need)
"""

import os
import sys
import logging
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict
from supabase import create_client, Client
from dotenv import load_dotenv

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.roster_scraper.roster_parser import get_position_credits, ALL_POSITIONS

load_dotenv()
logger = logging.getLogger(__name__)

# Ideal roster composition (~35 roster spots)
IDEAL_COUNTS = {
    'P': 14,
    'C': 3,
    '1B': 2,
    '2B': 2,
    'SS': 2,
    '3B': 2,
    'LF': 2,
    'CF': 2,
    'RF': 2,
    'DH': 1,
}

# Youth factor weights by normalized class year
# Higher value = more likely to need replacement
YOUTH_WEIGHTS = {
    1: 0.0,    # Freshman
    2: 0.25,   # Sophomore
    3: 0.50,   # Junior
    4: 1.0,    # Senior
    5: 1.0,    # Graduate
}

# Need score column names keyed by position
NEED_COLUMNS = {
    'P': 'need_pitcher',
    'C': 'need_catcher',
    '1B': 'need_first_base',
    '2B': 'need_second_base',
    'SS': 'need_shortstop',
    '3B': 'need_third_base',
    'LF': 'need_left_field',
    'CF': 'need_center_field',
    'RF': 'need_right_field',
    'DH': 'need_designated_hitter',
}


class PositionNeedsCalculator:
    """Computes position need scores from roster_players data"""

    def __init__(self):
        self._init_supabase()

    def _init_supabase(self):
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        self.supabase: Client = create_client(url, key)

    def compute_for_school(self, school_name: str, season: int) -> Optional[Dict]:
        """
        Compute position need scores for a single school/season.

        Returns:
            Dict ready for roster_position_needs upsert, or None on failure
        """
        players = self._get_roster(school_name, season)
        if not players:
            logger.warning(f"No roster data for {school_name} ({season})")
            return None

        return self._calculate_needs(players, school_name, season)

    def compute_all(self, season: int, division: Optional[int] = None) -> int:
        """
        Compute position needs for all schools with roster data.

        Args:
            season: Season year to compute for
            division: Optional division filter

        Returns:
            Number of schools processed
        """
        schools = self._get_schools_with_rosters(season, division)
        logger.info(f"Computing needs for {len(schools)} schools (season={season})")

        results = []
        for school_name in schools:
            result = self.compute_for_school(school_name, season)
            if result:
                results.append(result)

        if results:
            self._upsert_needs(results)

        logger.info(f"Computed needs for {len(results)}/{len(schools)} schools")
        return len(results)

    def _get_roster(self, school_name: str, season: int) -> List[Dict]:
        """Get roster players for a school/season"""
        try:
            response = self.supabase.table('roster_players') \
                .select('*') \
                .eq('school_name', school_name) \
                .eq('season', season) \
                .execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching roster for {school_name}: {e}")
            return []

    def _get_schools_with_rosters(self, season: int,
                                   division: Optional[int] = None) -> List[str]:
        """Get distinct school names that have roster data for a season"""
        try:
            query = self.supabase.table('roster_players') \
                .select('school_name') \
                .eq('season', season)
            if division is not None:
                query = query.eq('division', division)
            response = query.execute()
            rows = response.data or []
            return list({row['school_name'] for row in rows})
        except Exception as e:
            logger.error(f"Error fetching schools: {e}")
            return []

    def _calculate_needs(self, players: List[Dict], school_name: str,
                         season: int) -> Dict:
        """Core calculation: build position counts and compute need scores"""

        # Accumulators per position
        position_counts = defaultdict(float)      # total weighted count
        position_seniors = defaultdict(float)      # seniors/grads weighted count
        position_year_weights = defaultdict(list)  # class year weights for youth factor

        # Class year counters
        class_year_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

        for player in players:
            raw_pos = player.get('position') or player.get('normalized_position')
            norm_year = player.get('normalized_class_year')

            # Count class years
            if norm_year in class_year_counts:
                class_year_counts[norm_year] += 1

            # Get position credits (handles ambiguous positions)
            credits = get_position_credits(raw_pos)
            if not credits:
                continue

            for pos, credit in credits.items():
                position_counts[pos] += credit

                # Departure tracking (seniors = year 4 or 5)
                if norm_year is not None and norm_year >= 4:
                    position_seniors[pos] += credit

                # Youth factor tracking
                if norm_year is not None:
                    weight = YOUTH_WEIGHTS.get(norm_year, 0.5)
                    position_year_weights[pos].append((weight, credit))

        # Compute need scores per position
        need_scores = {}
        graduating_at_position = {}
        depth_by_position = {}

        for pos in ALL_POSITIONS:
            count = position_counts.get(pos, 0)
            seniors = position_seniors.get(pos, 0)
            ideal = IDEAL_COUNTS.get(pos, 2)

            # Departure factor (50%): what fraction are leaving?
            if count > 0:
                departure = seniors / count
            else:
                departure = 1.0  # No players = maximum need

            # Depth factor (30%): how far below ideal?
            if ideal > 0:
                depth = max(0.0, 1.0 - (count / ideal))
            else:
                depth = 0.0

            # Youth factor (20%): weighted average class year
            year_entries = position_year_weights.get(pos, [])
            if year_entries:
                total_weight = sum(w * c for w, c in year_entries)
                total_credit = sum(c for _, c in year_entries)
                youth = total_weight / total_credit if total_credit > 0 else 0.5
            else:
                youth = 0.5  # Default for unknown

            # Combined need score
            need = (departure * 0.50) + (depth * 0.30) + (youth * 0.20)
            need_scores[pos] = round(min(1.0, max(0.0, need)), 3)

            graduating_at_position[pos] = round(seniors, 1)
            depth_by_position[pos] = round(count, 1)

        # Get division from first player
        division = None
        for p in players:
            if p.get('division'):
                division = p['division']
                break

        # Build record
        pitcher_count = round(position_counts.get('P', 0))
        catcher_count = round(position_counts.get('C', 0))
        infielder_count = round(sum(position_counts.get(p, 0) for p in ['1B', '2B', 'SS', '3B']))
        outfielder_count = round(sum(position_counts.get(p, 0) for p in ['LF', 'CF', 'RF']))

        # Data quality assessment
        total = len(players)
        has_positions = sum(1 for p in players if p.get('position') or p.get('normalized_position'))
        has_years = sum(1 for p in players if p.get('normalized_class_year'))

        if has_positions >= total * 0.8 and has_years >= total * 0.8:
            data_quality = 'high'
        elif has_positions >= total * 0.5 and has_years >= total * 0.5:
            data_quality = 'medium'
        else:
            data_quality = 'low'

        record = {
            'school_name': school_name,
            'season': season,
            'division': division,
            'total_roster_size': total,
            'pitcher_count': pitcher_count,
            'catcher_count': catcher_count,
            'infielder_count': infielder_count,
            'outfielder_count': outfielder_count,
            'seniors_count': class_year_counts.get(4, 0) + class_year_counts.get(5, 0),
            'juniors_count': class_year_counts.get(3, 0),
            'sophomores_count': class_year_counts.get(2, 0),
            'freshmen_count': class_year_counts.get(1, 0),
            'graduating_at_position': graduating_at_position,
            'depth_by_position': depth_by_position,
            'data_quality': data_quality,
            'computed_at': datetime.now().isoformat(),
        }

        # Add need score columns
        for pos, col_name in NEED_COLUMNS.items():
            record[col_name] = need_scores.get(pos, 0.0)

        return record

    def _upsert_needs(self, records: List[Dict]):
        """Batch upsert position needs records"""
        batch_size = 50
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            try:
                response = self.supabase.table('roster_position_needs').upsert(
                    batch,
                    on_conflict='school_name,season'
                ).execute()
                if response.data:
                    logger.info(f"Upserted {len(batch)} position needs records")
            except Exception as e:
                logger.error(f"Error upserting needs batch: {e}")


def main():
    """Compute position needs for all schools with roster data"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    import argparse
    parser = argparse.ArgumentParser(description='Compute position need scores')
    parser.add_argument('--season', type=int, default=2026, help='Season year')
    parser.add_argument('--division', type=int, help='Filter by division (1, 2, 3)')
    parser.add_argument('--school', type=str, help='Single school name')
    args = parser.parse_args()

    calculator = PositionNeedsCalculator()

    if args.school:
        result = calculator.compute_for_school(args.school, args.season)
        if result:
            print(f"\nPosition needs for {args.school} ({args.season}):")
            for pos in ALL_POSITIONS:
                col = NEED_COLUMNS[pos]
                print(f"  {pos:4s}: {result[col]:.3f}")
            print(f"  Data quality: {result['data_quality']}")
            print(f"  Roster size: {result['total_roster_size']}")
        else:
            print(f"No data for {args.school}")
    else:
        count = calculator.compute_all(args.season, args.division)
        print(f"\nDone. Computed needs for {count} schools.")


if __name__ == "__main__":
    main()
