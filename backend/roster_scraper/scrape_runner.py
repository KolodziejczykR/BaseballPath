"""
Roster scrape orchestrator for BaseballPath
Scrapes rosters from configured schools, upserts to database,
then computes position needs.

Usage:
    python -m backend.roster_scraper.scrape_runner --division 1
    python -m backend.roster_scraper.scrape_runner --school "Alabama"
    python -m backend.roster_scraper.scrape_runner --all
"""

import os
import sys
import time
import logging
import argparse
from typing import List, Dict, Optional
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.roster_scraper.sidearm_scraper import SidearmRosterScraper
from backend.roster_scraper.roster_parser import normalize_player
from backend.roster_scraper.needs_calculator import PositionNeedsCalculator

load_dotenv()
logger = logging.getLogger(__name__)


class RosterScrapeRunner:
    """Orchestrates full roster scraping pipeline"""

    def __init__(self, season: int = 2026, headless: bool = True, delay: float = 3.0):
        self.season = season
        self.headless = headless
        self.delay = delay
        self._init_supabase()
        self.scraper = None

    def _init_supabase(self):
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        self.supabase: Client = create_client(url, key)

    def run(self, division: Optional[int] = None, school_name: Optional[str] = None,
            compute_needs: bool = True):
        """
        Run the full scrape pipeline.

        Args:
            division: Filter by division (1, 2, 3), or None for all
            school_name: Single school to scrape, or None for all active configs
            compute_needs: Whether to compute position needs after scraping
        """
        # Load configs
        configs = self._load_configs(division, school_name)
        if not configs:
            logger.warning("No active scrape configs found")
            return

        logger.info(f"Starting roster scrape: {len(configs)} schools, season={self.season}")

        # Track results
        success_count = 0
        fail_count = 0
        total_players = 0
        scraped_schools = []

        try:
            self.scraper = SidearmRosterScraper(
                headless=self.headless,
                delay=self.delay
            )

            for i, config in enumerate(configs):
                name = config['school_name']
                roster_url = config['roster_url']
                config_division = config.get('division')

                logger.info(f"[{i+1}/{len(configs)}] Scraping {name}...")

                try:
                    raw_players = self.scraper.scrape_roster(roster_url)

                    if raw_players:
                        # Normalize player records
                        normalized = []
                        for raw in raw_players:
                            record = normalize_player(
                                raw,
                                school_name=name,
                                season=self.season,
                                division=config_division,
                                source_url=roster_url
                            )
                            if record.get('player_name'):
                                normalized.append(record)

                        # Upsert to database
                        if normalized:
                            self._upsert_players(normalized)
                            total_players += len(normalized)

                        # Update config: success
                        self._update_config_status(
                            name, 'success', len(normalized)
                        )
                        success_count += 1
                        scraped_schools.append(name)
                        logger.info(f"  -> {len(normalized)} players saved")
                    else:
                        self._update_config_status(name, 'failed', 0)
                        fail_count += 1
                        logger.warning(f"  -> No players found")

                except Exception as e:
                    logger.error(f"  -> Error scraping {name}: {e}")
                    self._update_config_status(name, 'failed', 0)
                    fail_count += 1

                # Delay between schools (skip after last)
                if i < len(configs) - 1:
                    delay = self.delay + 2
                    time.sleep(delay)

        finally:
            if self.scraper:
                self.scraper.close()

        # Compute position needs
        if compute_needs and scraped_schools:
            logger.info("Computing position needs...")
            calculator = PositionNeedsCalculator()
            needs_count = calculator.compute_all(self.season, division)
            logger.info(f"Computed needs for {needs_count} schools")

        # Print summary
        print("\n" + "=" * 50)
        print("ROSTER SCRAPE SUMMARY")
        print("=" * 50)
        print(f"Season:         {self.season}")
        print(f"Schools found:  {len(configs)}")
        print(f"Successful:     {success_count}")
        print(f"Failed:         {fail_count}")
        print(f"Total players:  {total_players}")
        if compute_needs:
            print(f"Needs computed: {len(scraped_schools)}")
        print("=" * 50)

    def _load_configs(self, division: Optional[int] = None,
                      school_name: Optional[str] = None) -> List[Dict]:
        """Load active scrape configs from database"""
        try:
            query = self.supabase.table('roster_scrape_config') \
                .select('*') \
                .eq('is_active', True)

            if division is not None:
                query = query.eq('division', division)
            if school_name is not None:
                query = query.eq('school_name', school_name)

            response = query.execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error loading configs: {e}")
            return []

    def _upsert_players(self, players: List[Dict]):
        """Batch upsert player records"""
        batch_size = 50
        for i in range(0, len(players), batch_size):
            batch = players[i:i + batch_size]
            try:
                self.supabase.table('roster_players').upsert(
                    batch,
                    on_conflict='school_name,season,player_name,position'
                ).execute()
            except Exception as e:
                logger.error(f"Error upserting player batch: {e}")

    def _update_config_status(self, school_name: str, status: str,
                               player_count: int):
        """Update scrape config with latest status"""
        try:
            update = {
                'last_scrape_at': datetime.now().isoformat(),
                'last_scrape_status': status,
                'last_scrape_player_count': player_count,
            }

            if status == 'success':
                update['consecutive_failures'] = 0
            else:
                # Increment consecutive failures via read-modify-write
                response = self.supabase.table('roster_scrape_config') \
                    .select('consecutive_failures') \
                    .eq('school_name', school_name) \
                    .limit(1) \
                    .execute()
                current = 0
                if response.data:
                    current = response.data[0].get('consecutive_failures', 0) or 0
                update['consecutive_failures'] = current + 1

            self.supabase.table('roster_scrape_config') \
                .update(update) \
                .eq('school_name', school_name) \
                .execute()
        except Exception as e:
            logger.error(f"Error updating config status for {school_name}: {e}")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    parser = argparse.ArgumentParser(
        description='Scrape NCAA baseball rosters and compute position needs'
    )
    parser.add_argument('--division', type=int, choices=[1, 2, 3],
                        help='Filter by NCAA division')
    parser.add_argument('--school', type=str,
                        help='Scrape a single school by name')
    parser.add_argument('--all', action='store_true',
                        help='Scrape all active configs')
    parser.add_argument('--season', type=int, default=2026,
                        help='Season year (default: 2026)')
    parser.add_argument('--no-needs', action='store_true',
                        help='Skip position needs computation')
    parser.add_argument('--no-headless', action='store_true',
                        help='Run browser with GUI (for debugging)')
    parser.add_argument('--delay', type=float, default=3.0,
                        help='Base delay between requests (seconds)')
    args = parser.parse_args()

    # Validate: must specify --division, --school, or --all
    if not args.division and not args.school and not args.all:
        parser.error("Must specify --division, --school, or --all")

    runner = RosterScrapeRunner(
        season=args.season,
        headless=not args.no_headless,
        delay=args.delay,
    )

    runner.run(
        division=args.division,
        school_name=args.school,
        compute_needs=not args.no_needs,
    )


if __name__ == "__main__":
    main()
