"""
Selenium-based Massey Baseball Rankings Scraper
Uses the existing SeleniumDriverManager for browser automation
"""

import os
import sys
import time
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from supabase import create_client, Client
from dotenv import load_dotenv

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import existing selenium driver
from backend.school_info_scraper.selenium_driver import SeleniumDriverManager
from backend.baseball_rankings_scraper.utils.massey_rankings_xpaths import get_massey_link

load_dotenv()
logger = logging.getLogger(__name__)

class SeleniumMasseyBaseballScraper:
    """Selenium-based scraper using existing SeleniumDriverManager"""

    def __init__(self, headless: bool = False, delay: float = 3.0):
        """
        Initialize scraper with existing Selenium driver

        Args:
            headless: Run browser in headless mode
            delay: Base delay between requests
        """
        self.delay = delay
        self.driver_manager = None

        # Initialize Supabase client
        self._init_supabase()

        # Configuration for all requested years and divisions
        self.years = [2023, 2024, 2025]
        self.divisions = [1, 2, 3]

    def _init_supabase(self):
        """Initialize Supabase client"""
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")

        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")

        self.supabase: Client = create_client(url, key)
        self.table_name = "baseball_rankings_data"

    def _setup_driver(self, headless: bool = False):
        """Setup driver using existing manager"""
        try:
            self.driver_manager = SeleniumDriverManager(
                headless=headless,
                delay=self.delay,
                timeout=60  # Much longer timeout for slow loading
            )
            logger.info("✅ Selenium driver initialized successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to setup driver: {e}")
            return False

    def _wait_for_table_data(self, timeout: int = 45) -> bool:
        """Wait for rankings table to load with data"""
        try:
            logger.info(f"⏳ Waiting up to {timeout}s for table data...")

            driver = self.driver_manager.driver
            wait = WebDriverWait(driver, timeout)

            # Wait for table to exist
            wait.until(EC.presence_of_element_located((By.XPATH, "//table")))

            # Wait for team links (indicating data has loaded)
            def check_team_data(driver):
                try:
                    team_links = driver.find_elements(By.XPATH, "//table//tr/td[1]/a")
                    if len(team_links) >= 5:
                        logger.info(f"✅ Found {len(team_links)} team links - data loaded!")
                        return True

                    # Alternative check: rows with multiple cells
                    data_rows = driver.find_elements(By.XPATH, "//table//tr[count(td)>=6]")
                    if len(data_rows) >= 5:
                        logger.info(f"✅ Found {len(data_rows)} data rows - content loaded!")
                        return True

                    logger.debug(f"🔄 Still waiting... {len(team_links)} teams, {len(data_rows)} rows")
                    return False

                except Exception:
                    return False

            # Wait for data to appear
            wait.until(check_team_data)
            return True

        except TimeoutException:
            logger.warning(f"⏰ Timeout waiting for table data")

            # Debug: check what we actually have
            try:
                driver = self.driver_manager.driver
                tables = driver.find_elements(By.XPATH, "//table")
                logger.info(f"🔍 Found {len(tables)} tables on page")

                if tables:
                    rows = tables[0].find_elements(By.XPATH, ".//tr")
                    logger.info(f"🔍 First table has {len(rows)} rows")

                    # Save page source for debugging
                    with open("debug_selenium_page.html", "w") as f:
                        f.write(driver.page_source)
                    logger.info("💾 Page source saved to debug_selenium_page.html")

            except Exception as e:
                logger.error(f"Error in debug: {e}")

            return False

    def _parse_record(self, record_str: str) -> Tuple[Optional[int], Optional[int], Optional[float]]:
        """Parse record string into wins, losses, win percentage"""
        if not record_str or record_str.strip() == '':
            return None, None, None

        try:
            parts = record_str.strip().split('-')
            if len(parts) >= 2:
                wins = int(parts[0])
                losses = int(parts[1])
                total = wins + losses
                win_pct = round(wins / total, 3) if total > 0 else None
                return wins, losses, win_pct
        except (ValueError, IndexError):
            pass
        return None, None, None

    def _safe_float(self, value: str) -> Optional[float]:
        """Safely convert string to float"""
        if not value or value.strip() in ['', '-']:
            return None
        try:
            return float(value.strip())
        except (ValueError, TypeError):
            return None

    def scrape_division_year(self, year: int, division: int) -> List[Dict]:
        """Scrape rankings for a specific year and division"""
        if not self.driver_manager:
            if not self._setup_driver():
                return []

        logger.info(f"🎯 Scraping D{division} rankings for {year}...")

        url = get_massey_link(year, division)
        teams_data = []

        try:
            # Navigate to page with longer timeout and retry logic
            logger.info(f"🌐 Navigating to: {url}")

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    if self.driver_manager.get(url, custom_delay=5):
                        logger.info(f"📄 Loaded: {url}")
                        break
                    else:
                        logger.warning(f"⚠️ Load attempt {attempt + 1} failed")
                except Exception as e:
                    logger.warning(f"⚠️ Load attempt {attempt + 1} error: {e}")

                if attempt < max_retries - 1:
                    logger.info(f"🔄 Retrying in 10 seconds...")
                    time.sleep(10)
                else:
                    logger.error(f"❌ Failed to load page after {max_retries} attempts: {url}")
                    return []

            # Wait for data to load
            if not self._wait_for_table_data():
                logger.error(f"❌ No table data loaded for {year} D{division}")
                return []

            # Small additional delay for stability
            time.sleep(2)

            driver = self.driver_manager.driver

            # Find team rows (rows with links in first column)
            team_rows = driver.find_elements(By.XPATH, "//table//tr[td[1]/a]")
            logger.info(f"🔍 Found {len(team_rows)} team rows")

            for i, row in enumerate(team_rows):
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")

                    if len(cells) >= 6:
                        # Extract team name
                        team_name = None
                        try:
                            team_link = cells[0].find_element(By.TAG_NAME, "a")
                            team_name = team_link.text.strip()
                        except NoSuchElementException:
                            team_name = cells[0].text.strip()

                        if not team_name:
                            continue

                        # Use the specific tbody path like your console test to get correct row index
                        tbody_rows = driver.find_elements(By.XPATH, "/html/body/div[1]/div[3]/div[1]/table/tbody/tr")
                        actual_row_index = None
                        for idx, tbody_row in enumerate(tbody_rows, 1):
                            if tbody_row == row:
                                actual_row_index = idx
                                break

                        if actual_row_index is None:
                            logger.warning(f"Could not find tbody row index for team {team_name}")
                            continue

                        # Use the exact XPath structure from your console test
                        base_xpath = f"/html/body/div[1]/div[3]/div[1]/table/tbody/tr[{actual_row_index}]"

                        # Extract other fields using correct XPath for text nodes
                        # Record (column 2)
                        record = None
                        if len(cells) > 1:
                            record_text = driver.execute_script(
                                f"return document.evaluate('{base_xpath}/td[2]/text()[1]', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue?.nodeValue?.trim();"
                            )
                            record = record_text if record_text else None

                        # Overall Rating (column 3)
                        overall_rating = None
                        if len(cells) > 2:
                            rating_text = driver.execute_script(
                                f"return document.evaluate('{base_xpath}/td[3]/text()[1]', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue?.nodeValue?.trim();"
                            )
                            overall_rating = self._safe_float(rating_text)

                        # Power Rating (column 4)
                        power_rating = None
                        if len(cells) > 3:
                            power_text = driver.execute_script(
                                f"return document.evaluate('{base_xpath}/td[4]/text()[1]', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue?.nodeValue?.trim();"
                            )
                            power_rating = self._safe_float(power_text)

                        # Offensive Rating (column 5)
                        offensive_rating = None
                        if len(cells) > 4:
                            off_text = driver.execute_script(
                                f"return document.evaluate('{base_xpath}/td[5]/text()[1]', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue?.nodeValue?.trim();"
                            )
                            offensive_rating = self._safe_float(off_text)

                        # Defensive Rating (column 6)
                        defensive_rating = None
                        if len(cells) > 5:
                            def_text = driver.execute_script(
                                f"return document.evaluate('{base_xpath}/td[6]/text()[1]', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue?.nodeValue?.trim();"
                            )
                            defensive_rating = self._safe_float(def_text)

                        # Strength of Schedule (column 8)
                        strength_of_schedule = None
                        if len(cells) > 7:
                            sos_text = driver.execute_script(
                                f"return document.evaluate('{base_xpath}/td[8]/text()[1]', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue?.nodeValue?.trim();"
                            )
                            strength_of_schedule = self._safe_float(sos_text)

                        # Parse record
                        wins, losses, win_pct = self._parse_record(record)

                        team_data = {
                            'team_name': team_name,
                            'year': int(year),
                            'division': int(division),
                            'record': record,
                            'overall_rating': overall_rating,
                            'power_rating': power_rating,
                            'offensive_rating': offensive_rating,
                            'defensive_rating': defensive_rating,
                            'strength_of_schedule': strength_of_schedule,
                            'wins': wins,
                            'losses': losses,
                            'win_percentage': win_pct,
                            'scraped_at': datetime.now().isoformat(),
                            'data_source': 'massey_ratings_selenium'
                        }

                        teams_data.append(team_data)
                        logger.info(f"✅ Team {len(teams_data)}: {team_name}")

                except Exception as e:
                    logger.warning(f"⚠️ Error scraping row {i+1}: {e}")

            logger.info(f"🎉 Scraped {len(teams_data)} teams for {year} D{division}")

        except Exception as e:
            logger.error(f"❌ Error scraping {year} D{division}: {e}")

        return teams_data

    def upload_to_supabase(self, teams_data: List[Dict]) -> bool:
        """Upload teams data to Supabase"""
        if not teams_data:
            return True

        try:
            batch_size = 50
            for i in range(0, len(teams_data), batch_size):
                batch = teams_data[i:i + batch_size]

                response = self.supabase.table(self.table_name).upsert(
                    batch,
                    on_conflict='team_name,year,division'
                ).execute()

                if response.data:
                    logger.info(f"📤 Uploaded {len(batch)} teams")
                else:
                    logger.error(f"❌ Upload failed")
                    return False

            return True

        except Exception as e:
            logger.error(f"❌ Supabase error: {e}")
            return False

    def scrape_all_data(self) -> Dict[str, List[Dict]]:
        """Scrape all configured years and divisions"""
        logger.info(f"🚀 Starting scrape: years {self.years}, divisions {self.divisions}")

        all_data = {}
        total_teams = 0

        try:
            for year in self.years:
                for division in self.divisions:
                    key = f"{year}_D{division}"

                    # Delay between combinations
                    if total_teams > 0:
                        time.sleep(self.delay + 2)

                    teams_data = self.scrape_division_year(year, division)
                    all_data[key] = teams_data
                    total_teams += len(teams_data)

                    # Upload after each combination
                    if teams_data:
                        self.upload_to_supabase(teams_data)

        finally:
            self.cleanup()

        logger.info(f"🎉 Total teams scraped: {total_teams}")
        return all_data

    def cleanup(self):
        """Cleanup resources"""
        if self.driver_manager:
            try:
                self.driver_manager.close()  # Use close() not quit()
                logger.info("🧹 Driver cleaned up")
            except Exception as e:
                logger.warning(f"⚠️ Cleanup error: {e}")

def main():
    """Run the full Selenium scraper for all years and divisions"""
    try:
        # Run with headless browser for full scrape
        scraper = SeleniumMasseyBaseballScraper(headless=True, delay=3.0)

        # Use the configured years and divisions (2023-2025, D1-D3)
        results = scraper.scrape_all_data()

        print("\n" + "="*50)
        print("SELENIUM MASSEY SCRAPER RESULTS")
        print("="*50)

        for key, teams in results.items():
            print(f"{key}: {len(teams)} teams")
            if teams:
                print(f"  Sample: {teams[0]['team_name']}")

        total = sum(len(teams) for teams in results.values())
        print(f"\nTotal: {total} teams")

        return results

    except Exception as e:
        logger.error(f"❌ Main error: {e}")
        return {}

if __name__ == "__main__":
    main()