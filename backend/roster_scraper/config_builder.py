"""
Config builder for roster scraping
Reads school_data_general.school_athletics_page + name mappings,
populates roster_scrape_config with roster URLs.
"""

import os
import sys
import logging
from typing import List, Dict, Optional
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

load_dotenv()
logger = logging.getLogger(__name__)


class RosterConfigBuilder:
    """Builds roster_scrape_config entries from existing school data"""

    def __init__(self):
        self._init_supabase()

    def _init_supabase(self):
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        self.supabase: Client = create_client(url, key)

    def build_configs(self, division_filter: Optional[int] = None) -> int:
        """
        Build roster_scrape_config entries for schools with athletics URLs.

        Args:
            division_filter: If set, only build configs for this division (1, 2, or 3)

        Returns:
            Number of configs upserted
        """
        # Step 1: Get all schools with athletics URLs
        schools = self._get_schools_with_athletics_urls()
        logger.info(f"Found {len(schools)} schools with athletics URLs")

        if not schools:
            logger.warning("No schools found with school_athletics_page populated")
            return 0

        # Step 2: Get name mappings (school_name -> team_name)
        name_mappings = self._get_name_mappings()
        logger.info(f"Loaded {len(name_mappings)} school-to-team name mappings")

        # Step 3: Get division info from rankings data
        division_map = self._get_division_map()
        logger.info(f"Loaded division info for {len(division_map)} teams")

        # Step 4: Build config records
        configs = []
        for school in schools:
            school_name = school.get('school_name')
            athletics_url = school.get('school_athletics_page', '').strip().rstrip('/')

            if not school_name or not athletics_url:
                continue

            # Look up team name from mapping
            team_name = name_mappings.get(school_name)

            # Look up division from rankings data (via team name)
            division = None
            if team_name:
                division = division_map.get(team_name)

            # Apply division filter if specified
            if division_filter is not None and division != division_filter:
                continue

            # Build roster URL
            roster_url = f"{athletics_url}/sports/baseball/roster"

            config = {
                'school_name': school_name,
                'team_name': team_name,
                'division': division,
                'athletics_url': athletics_url,
                'roster_url': roster_url,
                'platform': 'sidearm',
                'is_active': True,
                'requires_selenium': True,
            }
            configs.append(config)

        if not configs:
            logger.warning("No configs to upsert")
            return 0

        # Step 5: Batch upsert
        upserted = self._upsert_configs(configs)
        logger.info(f"Upserted {upserted} roster scrape configs")
        return upserted

    def _get_schools_with_athletics_urls(self) -> List[Dict]:
        """Get schools that have school_athletics_page populated"""
        try:
            response = self.supabase.table('school_data_general') \
                .select('school_name, school_athletics_page') \
                .not_.is_('school_athletics_page', 'null') \
                .execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching schools: {e}")
            return []

    def _get_name_mappings(self) -> Dict[str, str]:
        """Get school_name -> team_name mappings"""
        try:
            response = self.supabase.table('school_baseball_ranking_name_mapping') \
                .select('school_name, team_name') \
                .not_.is_('team_name', 'null') \
                .execute()
            rows = response.data or []
            return {row['school_name']: row['team_name'] for row in rows if row.get('school_name')}
        except Exception as e:
            logger.error(f"Error fetching name mappings: {e}")
            return {}

    def _get_division_map(self) -> Dict[str, int]:
        """
        Get team_name -> division (int) from baseball_rankings_data.
        Maps division_group strings to integers.
        """
        try:
            response = self.supabase.table('baseball_rankings_data') \
                .select('team_name, division') \
                .execute()
            rows = response.data or []

            division_map = {}
            for row in rows:
                team = row.get('team_name')
                div = row.get('division')
                if team and div:
                    division_map[team] = int(div)
            return division_map
        except Exception as e:
            logger.error(f"Error fetching division data: {e}")
            return {}

    def _upsert_configs(self, configs: List[Dict]) -> int:
        """Batch upsert configs into roster_scrape_config"""
        batch_size = 50
        total = 0

        for i in range(0, len(configs), batch_size):
            batch = configs[i:i + batch_size]
            try:
                response = self.supabase.table('roster_scrape_config').upsert(
                    batch,
                    on_conflict='school_name'
                ).execute()
                if response.data:
                    total += len(response.data)
                    logger.info(f"Upserted batch of {len(batch)} configs")
            except Exception as e:
                logger.error(f"Error upserting batch: {e}")

        return total


def main():
    """Build roster scrape configs from school data"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    builder = RosterConfigBuilder()
    count = builder.build_configs()
    print(f"\nDone. Upserted {count} roster scrape configs.")


if __name__ == "__main__":
    main()
