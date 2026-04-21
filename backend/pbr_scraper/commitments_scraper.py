"""
Commitments page scraper for PBR
Scrapes the /commitments page to collect player profile URLs and basic info.
Pagination is AJAX-driven via getCommitments() JS function.
"""

import csv
import logging
import os
import time
from typing import Dict, List, Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
)

from backend.pbr_scraper.config import (
    PBR_BASE_URL,
    CLASS_YEARS,
    BETWEEN_PAGES_DELAY,
    PAGE_LOAD_DELAY,
    COMMITMENTS_CSV_PATH,
    OUTPUT_DIR,
)

logger = logging.getLogger(__name__)


class CommitmentsScraper:
    """Scrapes the PBR commitments page to collect player URLs"""

    def __init__(self, driver_manager):
        self.driver_manager = driver_manager

    def scrape_all_classes(
        self, class_years: List[int] = None
    ) -> List[Dict[str, str]]:
        """
        Scrape commitment listings for all specified class years.

        Args:
            class_years: List of graduation years to scrape. Defaults to config.

        Returns:
            List of dicts with player basic info + profile URL
        """
        years = class_years or CLASS_YEARS
        all_players = []

        for year in years:
            logger.info(f"=== Scraping class of {year} ===")
            players = self._scrape_class_year(year)
            all_players.extend(players)
            logger.info(f"Class {year}: {len(players)} committed players found")

            # Save incrementally after each class year so progress isn't lost
            self._save_to_csv(all_players)
            logger.info(f"Saved {len(all_players)} total players to CSV so far")

            time.sleep(BETWEEN_PAGES_DELAY)

        logger.info(f"Total committed players collected: {len(all_players)}")

        return all_players

    def _scrape_class_year(self, year: int) -> List[Dict[str, str]]:
        """Scrape all pages of commitments for a single class year"""
        url = f"{PBR_BASE_URL}/commitments"

        # Navigate to commitments page
        if not self.driver_manager.get(url, custom_delay=PAGE_LOAD_DELAY):
            logger.error(f"Failed to load commitments page")
            return []

        driver = self.driver_manager.driver

        # Wait for the table to load
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "tbody.result-data tr")
                )
            )
        except TimeoutException:
            logger.error("Commitments table never loaded")
            return []

        # Select the class year from the dropdown
        try:
            class_select = Select(driver.find_element(By.ID, "ranking_class"))
            class_select.select_by_value(str(year))
            # Wait for AJAX to fire and replace the table content
            time.sleep(PAGE_LOAD_DELAY + 2)

            # Wait for updated pagination to appear
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "span.page-total")
                )
            )
            # Extra wait for table rows to populate
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "tbody.result-data tr")
                )
            )
        except Exception as e:
            logger.error(f"Failed to select class year {year}: {e}")
            return []

        # Get total pages (read after AJAX has updated the container)
        time.sleep(1)
        total_pages = self._get_total_pages(driver)
        logger.info(f"Class {year}: {total_pages} pages to scrape")

        all_players = []
        current_page = 1

        while current_page <= total_pages:
            logger.info(f"Class {year} - Page {current_page}/{total_pages}")

            # Scrape current page
            players = self._scrape_current_page(driver, year)
            all_players.extend(players)

            if current_page >= total_pages:
                break

            # Navigate to next page
            if not self._go_to_next_page(driver, current_page + 1):
                logger.warning(
                    f"Failed to navigate to page {current_page + 1}, stopping"
                )
                break

            current_page += 1
            time.sleep(BETWEEN_PAGES_DELAY)

        return all_players

    def _get_total_pages(self, driver) -> int:
        """Extract total page count from pagination text 'Page 1 of 1086'"""
        import re

        # Try Selenium element first
        try:
            page_total = driver.find_element(
                By.CSS_SELECTOR, "span.page-total"
            )
            text = page_total.text.strip()
            logger.info(f"Pagination text: '{text}'")
            # "Page 1 of 1086"
            parts = text.split("of")
            if len(parts) == 2:
                return int(parts[1].strip())
        except Exception as e:
            logger.warning(f"Could not get total pages via element: {e}")

        # Fallback: regex on page source
        try:
            source = driver.page_source
            match = re.search(r'Page\s+\d+\s+of\s+(\d+)', source)
            if match:
                total = int(match.group(1))
                logger.info(f"Total pages from source: {total}")
                return total
        except Exception:
            pass

        # Fallback: count pagination buttons
        try:
            pages = driver.find_elements(By.CSS_SELECTOR, "li.pge.page-item")
            if pages:
                last_page = max(
                    int(p.get_attribute("data-page"))
                    for p in pages
                    if p.get_attribute("data-page")
                )
                logger.info(f"Total pages from buttons: {last_page}")
                return last_page
        except Exception:
            pass

        logger.warning("Could not determine total pages, defaulting to 1")
        return 1

    def _scrape_current_page(
        self, driver, class_year: int
    ) -> List[Dict[str, str]]:
        """Scrape all player rows from the current commitments page"""
        players = []

        try:
            rows = driver.find_elements(
                By.CSS_SELECTOR, "tbody.result-data tr"
            )

            for row in rows:
                try:
                    player = self._parse_row(row, class_year)
                    if player and player.get("profile_url"):
                        players.append(player)
                except StaleElementReferenceException:
                    continue
                except Exception as e:
                    logger.debug(f"Error parsing row: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error scraping page: {e}")

        return players

    def _parse_row(
        self, row, class_year: int
    ) -> Optional[Dict[str, str]]:
        """
        Parse a single table row from the commitments page.

        Expected HTML:
            <tr>
                <td><a href="/profiles/PA/Tom-Aaron-7124893065">Tom Aaron</a></td>
                <td>PA</td>
                <td>Perkiomen</td>
                <td>2015</td>
                <td>3B</td>
                <td><a href="/schools/some-school">School Name</a></td>
            </tr>
        """
        cells = row.find_elements(By.TAG_NAME, "td")
        if len(cells) < 6:
            return None

        # Player name + profile link
        player_name = ""
        profile_url = ""
        try:
            link = cells[0].find_element(By.TAG_NAME, "a")
            player_name = link.text.strip()
            href = link.get_attribute("href")
            if href and "/profiles/" in href:
                profile_url = href
        except NoSuchElementException:
            return None

        if not profile_url:
            return None

        # State
        state = cells[1].text.strip()

        # High school
        high_school = cells[2].text.strip()

        # Class year from table (should match filter but grab it anyway)
        table_class = cells[3].text.strip()

        # Position
        position = cells[4].text.strip()

        # Committed school + school link
        committed_school = ""
        school_link = ""
        try:
            school_a = cells[5].find_element(By.TAG_NAME, "a")
            committed_school = school_a.text.strip()
            school_href = school_a.get_attribute("href")
            if school_href:
                # Store relative path for cache key
                if "/schools/" in school_href:
                    school_link = school_href.split(".com")[-1] if ".com" in school_href else school_href
        except NoSuchElementException:
            committed_school = cells[5].text.strip()

        return {
            "name": player_name,
            "profile_url": profile_url,
            "player_state": state,
            "high_school": high_school,
            "class": table_class or str(class_year),
            "primary_position": position,
            "commitment": committed_school,
            "school_link": school_link,
        }

    def _go_to_next_page(self, driver, target_page: int) -> bool:
        """
        Navigate to the next page of commitments.
        Uses JavaScript to call getCommitments() directly since pagination
        is AJAX-driven.
        """
        try:
            # Grab first player name on current page to detect when it changes
            old_first_name = ""
            try:
                first_row = driver.find_element(
                    By.CSS_SELECTOR, "tbody.result-data tr td a"
                )
                old_first_name = first_row.text.strip()
            except Exception:
                pass

            # Use JavaScript to call getCommitments directly.
            # Selenium .click() fails because the pagination is off-screen
            # ("element click intercepted"), so we bypass it entirely.
            driver.execute_script(
                f"getCommitments('1', 100, {target_page});"
            )

            # Wait for table content to change
            time.sleep(PAGE_LOAD_DELAY + 1)

            # Wait for rows to appear
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "tbody.result-data tr")
                )
            )

            # Verify content actually changed (if we had a reference)
            if old_first_name:
                try:
                    new_first = driver.find_element(
                        By.CSS_SELECTOR, "tbody.result-data tr td a"
                    )
                    if new_first.text.strip() == old_first_name:
                        # Content didn't change, wait a bit more
                        time.sleep(3)
                except Exception:
                    pass

            return True

        except Exception as e:
            logger.error(f"Failed to navigate to page {target_page}: {e}")
            return False

    def _save_to_csv(self, players: List[Dict[str, str]]):
        """Save collected player URLs to CSV"""
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        fieldnames = [
            "name", "profile_url", "player_state", "high_school",
            "class", "primary_position", "commitment", "school_link",
        ]

        with open(COMMITMENTS_CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(players)

        logger.info(f"Saved {len(players)} player URLs to {COMMITMENTS_CSV_PATH}")

    @staticmethod
    def load_from_csv() -> List[Dict[str, str]]:
        """Load previously saved player URLs from CSV"""
        if not os.path.exists(COMMITMENTS_CSV_PATH):
            return []

        players = []
        with open(COMMITMENTS_CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                players.append(dict(row))

        logger.info(f"Loaded {len(players)} player URLs from {COMMITMENTS_CSV_PATH}")
        return players
