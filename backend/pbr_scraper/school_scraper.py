"""
School info scraper for PBR
Scrapes /schools/{slug} pages for conference + division info.
Results are cached in a JSON file to avoid re-scraping.
"""

import json
import os
import logging
import re
import time
from typing import Dict, Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from backend.pbr_scraper.config import (
    PBR_BASE_URL,
    SCHOOL_CACHE_PATH,
    OUTPUT_DIR,
    PAGE_LOAD_DELAY,
)

logger = logging.getLogger(__name__)


class SchoolScraper:
    """Scrapes and caches school conference/division info from PBR school pages"""

    def __init__(self, driver_manager):
        self.driver_manager = driver_manager
        self.cache: Dict[str, Dict] = {}
        self._load_cache()

    def _load_cache(self):
        """Load existing school cache from disk"""
        if os.path.exists(SCHOOL_CACHE_PATH):
            with open(SCHOOL_CACHE_PATH, "r") as f:
                self.cache = json.load(f)
            logger.info(f"Loaded {len(self.cache)} schools from cache")

    def _save_cache(self):
        """Save school cache to disk"""
        os.makedirs(os.path.dirname(SCHOOL_CACHE_PATH), exist_ok=True)
        with open(SCHOOL_CACHE_PATH, "w") as f:
            json.dump(self.cache, f, indent=2)

    def get_school_info(self, school_slug: str) -> Dict[str, Optional[str]]:
        """
        Get school info (conference, division, location).
        Returns cached result if available, otherwise scrapes the page.

        Args:
            school_slug: The school URL path, e.g., "/schools/stony-brook"

        Returns:
            Dict with keys: conference, division, location
        """
        # Normalize slug
        if school_slug.startswith("/"):
            school_slug = school_slug.lstrip("/")
        if school_slug.startswith("schools/"):
            cache_key = school_slug
        else:
            cache_key = f"schools/{school_slug}"

        # Check cache
        if cache_key in self.cache:
            return self.cache[cache_key]

        # Scrape
        info = self._scrape_school(cache_key)
        self.cache[cache_key] = info
        self._save_cache()
        return info

    def _scrape_school(self, school_path: str) -> Dict[str, Optional[str]]:
        """
        Scrape a single school page.

        Expected HTML structure:
            <h2 class="player-subtitle">Stony Brook, NY</h2>
            <ul class="data-list">
                <li><strong>Conference:</strong> America East</li>
                <li><strong>Division:</strong> NCAA I</li>
            </ul>
        """
        url = f"{PBR_BASE_URL}/{school_path}"
        logger.info(f"Scraping school: {url}")

        result = {
            "conference": None,
            "division": None,
            "location": None,
        }

        try:
            if not self.driver_manager.get(url, custom_delay=PAGE_LOAD_DELAY):
                logger.warning(f"Failed to load school page: {url}")
                return result

            driver = self.driver_manager.driver

            # Extract location from subtitle
            try:
                subtitle = driver.find_element(By.CSS_SELECTOR, "h2.player-subtitle")
                result["location"] = subtitle.text.strip()
            except Exception:
                pass

            # Wait for the data-list to appear
            try:
                WebDriverWait(driver, 8).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "ul.data-list li")
                    )
                )
            except TimeoutException:
                logger.debug(f"data-list not found via wait, trying page source fallback")

            # Try Selenium element extraction first
            try:
                list_items = driver.find_elements(By.CSS_SELECTOR, "ul.data-list li")
                for li in list_items:
                    text = li.text.strip()
                    if text.startswith("Conference:"):
                        result["conference"] = text.replace("Conference:", "").strip()
                    elif text.startswith("Division:"):
                        result["division"] = text.replace("Division:", "").strip()
            except Exception:
                pass

            # Fallback: parse page source with regex if Selenium didn't find it
            if not result["conference"] or not result["division"]:
                try:
                    source = driver.page_source
                    conf_match = re.search(
                        r"<strong>Conference:</strong>\s*(.+?)</li>", source
                    )
                    div_match = re.search(
                        r"<strong>Division:</strong>\s*(.+?)</li>", source
                    )
                    if conf_match and not result["conference"]:
                        result["conference"] = conf_match.group(1).strip()
                    if div_match and not result["division"]:
                        result["division"] = div_match.group(1).strip()
                except Exception:
                    pass

            logger.info(
                f"School {school_path}: "
                f"{result['division']} / {result['conference']} / {result['location']}"
            )

        except Exception as e:
            logger.error(f"Error scraping school {school_path}: {e}")

        return result

    def bulk_scrape(self, school_slugs: list) -> Dict[str, Dict]:
        """
        Scrape multiple schools, skipping those already cached.

        Args:
            school_slugs: List of school URL paths

        Returns:
            Dict of all school info (cached + newly scraped)
        """
        uncached = []
        for slug in school_slugs:
            normalized = slug.lstrip("/")
            if not normalized.startswith("schools/"):
                normalized = f"schools/{normalized}"
            if normalized not in self.cache:
                uncached.append(normalized)

        if uncached:
            logger.info(
                f"Need to scrape {len(uncached)} schools "
                f"({len(school_slugs) - len(uncached)} already cached)"
            )

            for i, slug in enumerate(uncached):
                info = self._scrape_school(slug)
                self.cache[slug] = info

                # Save cache periodically
                if (i + 1) % 25 == 0:
                    self._save_cache()
                    logger.info(f"Progress: {i + 1}/{len(uncached)} schools scraped")

                # Brief delay between requests
                time.sleep(1.0)

            self._save_cache()
            logger.info(f"Finished scraping {len(uncached)} schools")

        return {
            slug: self.cache.get(
                slug.lstrip("/") if not slug.startswith("schools/")
                else slug
            )
            for slug in school_slugs
        }

    @property
    def cache_size(self) -> int:
        return len(self.cache)
