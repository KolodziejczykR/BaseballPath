"""
Player profile scraper for PBR
Scrapes individual player profile pages for bio info and all Best Of stats with dates.
"""

import logging
import re
import time
from typing import Dict, List, Optional, Tuple

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
)

from backend.pbr_scraper.config import (
    PAGE_LOAD_DELAY,
    PITCH_SECTIONS,
    PITCH_STAT_SUFFIX,
    STAT_LABEL_MAP,
    ALL_STAT_COLUMNS,
)

logger = logging.getLogger(__name__)


class ProfileScraper:
    """Scrapes individual PBR player profile pages"""

    def __init__(self, driver_manager):
        self.driver_manager = driver_manager

    def scrape_profile(self, url: str) -> Optional[Dict]:
        """
        Scrape a single player profile page.

        Args:
            url: Full URL to the player profile

        Returns:
            Dict with all player data, or None on failure
        """
        if not self.driver_manager.get(url, custom_delay=PAGE_LOAD_DELAY):
            logger.warning(f"Failed to load profile: {url}")
            return None

        driver = self.driver_manager.driver

        # Verify we're on a profile page
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div.profile-top")
                )
            )
        except TimeoutException:
            logger.warning(f"Profile page did not load properly: {url}")
            return None

        # Scroll down to ensure Best Of section loads (it may lazy-load)
        try:
            driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight / 2);"
            )
            time.sleep(1.0)
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.5)
        except Exception:
            pass

        # Wait for Best Of stats to appear
        try:
            WebDriverWait(driver, 8).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "section.bestof-chart article.stat-item")
                )
            )
        except TimeoutException:
            logger.debug(f"No bestof-chart stats found (player may have no stats): {url}")

        # Build player data dict
        player = {"link": url}

        # Initialize all stat columns to None
        for col in ALL_STAT_COLUMNS:
            player[col] = None
            player[f"{col}_date"] = None

        # Extract bio
        bio = self._extract_bio(driver)
        player.update(bio)

        # Extract commitment
        commitment = self._extract_commitment(driver)
        player.update(commitment)

        # Extract Best Of stats with dates
        stats = self._extract_best_of_stats(driver)
        player.update(stats)

        # Extract event history
        events = self._extract_events(driver)
        player["events"] = events

        return player

    def _extract_bio(self, driver) -> Dict:
        """
        Extract player bio info from the profile header.
        Uses regex on the full data-list text rather than delimiter splitting
        for robustness against different bullet/whitespace characters.
        """
        bio = {
            "name": "",
            "class": "",
            "positions": "",
            "high_school": "",
            "player_state": "",
            "height": None,
            "weight": None,
            "throwing_hand": "",
            "hitting_handedness": "",
            "age": "",
        }

        # Player name
        try:
            name_input = driver.find_element(By.ID, "current_player_name")
            bio["name"] = name_input.get_attribute("value").strip()
        except NoSuchElementException:
            try:
                name_el = driver.find_element(By.CSS_SELECTOR, "h1.player-name")
                bio["name"] = name_el.text.replace("\n", " ").strip()
            except NoSuchElementException:
                pass

        # Class year
        try:
            class_el = driver.find_element(
                By.CSS_SELECTOR, "div.class-of-row h2"
            )
            text = class_el.text.strip()
            match = re.search(r"(\d{4})", text)
            if match:
                bio["class"] = int(match.group(1))
        except NoSuchElementException:
            pass

        # Positions
        try:
            pos_elements = driver.find_elements(
                By.CSS_SELECTOR, "div.player-position"
            )
            positions = [p.text.strip() for p in pos_elements if p.text.strip()]
            bio["positions"] = ",".join(positions)
        except Exception:
            pass

        # Parse the data-list div using innerHTML for more reliable parsing
        try:
            data_list = driver.find_element(By.CSS_SELECTOR, "div.data-list")
            inner_html = data_list.get_attribute("innerHTML")
            text_content = data_list.get_attribute("textContent").strip()
            bio.update(self._parse_data_list(inner_html, text_content))
        except NoSuchElementException:
            pass

        return bio

    def _parse_data_list(self, inner_html: str, text_content: str) -> Dict:
        """
        Parse the data-list using regex on both innerHTML and textContent.

        innerHTML example:
            <br> Don Bosco Prep (HS) &bullet; NJ<br>
            <img class="verified_height" .../>
            6' 1"  &bullet; 215LBS<br>
            R/R &bullet; 20yr
            <br>
            Travel Team: Richmond Braves<br>
        """
        result = {
            "high_school": "",
            "player_state": "",
            "height": None,
            "weight": None,
            "throwing_hand": "",
            "hitting_handedness": "",
            "age": "",
        }

        # Normalize the full text for regex matching
        text = re.sub(r"\s+", " ", text_content).strip()

        # --- High school: look for "(HS)" marker in HTML ---
        hs_match = re.search(r"([^<>•\u2022|]+?)\s*\(HS\)", inner_html)
        if hs_match:
            result["high_school"] = hs_match.group(1).strip()

        # --- State: 2-letter code near the school name or in the URL ---
        # Look for pattern like "• NJ" or "NJ<br" in the HTML
        state_match = re.search(
            r"(?:&bullet;|•|\u2022)\s*([A-Z]{2})\s*(?:<br|$)", inner_html
        )
        if state_match:
            result["player_state"] = state_match.group(1)

        # --- Height: "6' 1"" or "5' 11"" pattern ---
        height_match = re.search(r"(\d+)['\u2019]\s*(\d+)", text)
        if height_match:
            feet = int(height_match.group(1))
            inches = int(height_match.group(2))
            result["height"] = feet * 12 + inches

        # --- Weight: "215LBS" or "215 LBS" ---
        weight_match = re.search(r"(\d{2,3})\s*(?:LBS|lbs|Lbs)", text)
        if weight_match:
            result["weight"] = int(weight_match.group(1))

        # --- Bats/Throws: "R/R", "L/R", "S/R", "R/L" ---
        bt_match = re.search(r"(?:^|\s)([RLS])/([RL])(?:\s|$)", text)
        if bt_match:
            result["hitting_handedness"] = bt_match.group(1)
            result["throwing_hand"] = bt_match.group(2)

        # --- Age: "20yr" or "18yr 5mo" ---
        age_match = re.search(r"(\d+yr(?:\s*\d+mo)?)", text)
        if age_match:
            result["age"] = age_match.group(1)

        return result

    def _extract_commitment(self, driver) -> Dict:
        """
        Extract commitment info.

        Some profiles show:
            <a class="player-university" href="/schools/stony-brook">Stony Brook</a>
        Others show the commit date in a separate element:
            <a class="player-university" href="/schools/virginia">(11/12/25)</a>
        We extract both the school name and any commitment date.
        """
        result = {
            "commitment": "",
            "commitment_date": "",
            "school_link": "",
        }

        try:
            # Find all commitment slides (there may be multiple)
            slides = driver.find_elements(
                By.CSS_SELECTOR, "div.commitment-slide"
            )

            for slide in slides:
                try:
                    school_el = slide.find_element(
                        By.CSS_SELECTOR, "a.player-university"
                    )
                    text = school_el.text.strip()
                    href = school_el.get_attribute("href") or ""

                    # Check if this text is a date like "(11/12/25)"
                    date_match = re.match(
                        r"^\(?(\d{1,2}/\d{1,2}/\d{2,4})\)?$", text
                    )
                    if date_match:
                        result["commitment_date"] = date_match.group(1)
                    elif text and not text.startswith("("):
                        result["commitment"] = text
                        if "/schools/" in href:
                            result["school_link"] = (
                                href.split(".com")[-1]
                                if ".com" in href
                                else href
                            )
                except NoSuchElementException:
                    continue

            # If we only got a date but no school name, try to get school
            # from the first player-university link with an href
            if not result["commitment"] and not result["school_link"]:
                try:
                    all_links = driver.find_elements(
                        By.CSS_SELECTOR, "a.player-university"
                    )
                    for link in all_links:
                        href = link.get_attribute("href") or ""
                        if "/schools/" in href:
                            result["school_link"] = (
                                href.split(".com")[-1]
                                if ".com" in href
                                else href
                            )
                            # Derive school name from slug
                            slug = href.rstrip("/").split("/")[-1]
                            result["commitment"] = slug.replace("-", " ").title()
                            break
                except Exception:
                    pass

        except Exception:
            # Fallback: try single element approach
            try:
                school_el = driver.find_element(
                    By.CSS_SELECTOR, "a.player-university"
                )
                result["commitment"] = school_el.text.strip()
                href = school_el.get_attribute("href") or ""
                if "/schools/" in href:
                    result["school_link"] = (
                        href.split(".com")[-1] if ".com" in href else href
                    )
            except NoSuchElementException:
                pass

        return result

    def _extract_best_of_stats(self, driver) -> Dict:
        """
        Extract all Best Of stats with dates.
        Uses page source regex as primary method since Selenium .text can miss
        content in elements that aren't fully rendered/visible.
        """
        stats = {}

        # Try Selenium approach first
        self._extract_stats_selenium(driver, stats)

        # Always run regex fallback for pitching section to catch offspeed
        # stats that Selenium may miss (h4.text case mismatch, etc.).
        # The regex path only overwrites empty/None values, so Selenium
        # results are preserved.
        self._extract_stats_from_source(driver, stats)

        return stats

    def _extract_stats_selenium(self, driver, stats: Dict):
        """Extract stats using Selenium element finding"""
        # Pitching stats (context-dependent labels)
        self._extract_pitching_stats(driver, stats)

        # Non-pitching stats (unique labels)
        for section_class in [
            "bestof-chart__power",
            "bestof-chart__hit",
            "bestof-chart__run",
            "bestof-chart__defense",
        ]:
            self._extract_section_stats(driver, section_class, stats)

    def _extract_stats_from_source(self, driver, stats: Dict):
        """
        Fallback: parse stats with dates from page source HTML using regex.
        This handles cases where Selenium can't read the text content.

        Pattern:
            <article class="stat-item">
                <div class="stat-v ">92</div>
                <div class="stat-label">Velocity (max)</div>
                <div class="stat-date">3/23/25</div>
            </article>
        """
        try:
            source = driver.page_source
        except Exception:
            return

        # Find all stat-item blocks
        pattern = re.compile(
            r'<article\s+class="stat-item">\s*'
            r'<div\s+class="stat-v[^"]*">\s*(.*?)\s*</div>\s*'
            r'<div\s+class="stat-label">\s*(.*?)\s*</div>\s*'
            r'<div\s+class="stat-date">\s*(.*?)\s*</div>\s*'
            r'</article>',
            re.DOTALL,
        )

        # We need context to know which section a stat belongs to.
        # Extract the bestof-chart sections separately.

        # --- Pitching section ---
        pitch_match = re.search(
            r'class="bestof-chart__row bestof-chart__pitching">(.*?)'
            r'(?=class="bestof-chart__row bestof-chart__|$)',
            source, re.DOTALL,
        )
        if pitch_match:
            pitch_html = pitch_match.group(1)
            self._parse_pitching_from_html(pitch_html, stats)

        # --- Non-pitching sections ---
        section_map = {
            "bestof-chart__power": STAT_LABEL_MAP,
            "bestof-chart__hit": STAT_LABEL_MAP,
            "bestof-chart__run": STAT_LABEL_MAP,
            "bestof-chart__defense": STAT_LABEL_MAP,
        }
        for section_class, label_map in section_map.items():
            section_match = re.search(
                rf'class="bestof-chart__row {section_class}">(.*?)'
                r'(?=class="bestof-chart__row bestof-chart__|</section>)',
                source, re.DOTALL,
            )
            if section_match:
                section_html = section_match.group(1)
                for m in pattern.finditer(section_html):
                    value = m.group(1).strip()
                    label = m.group(2).strip()
                    date = m.group(3).strip() or None

                    if value in ("-", ""):
                        continue

                    col_name = label_map.get(label)
                    if col_name and not stats.get(col_name):
                        stats[col_name] = self._clean_stat_value(value)
                        stats[f"{col_name}_date"] = date

    def _parse_pitching_from_html(self, pitch_html: str, stats: Dict):
        """Parse pitching stats from HTML, handling pitch-type subsections"""
        stat_pattern = re.compile(
            r'<article\s+class="stat-item">\s*'
            r'<div\s+class="stat-v[^"]*">\s*(.*?)\s*</div>\s*'
            r'<div\s+class="stat-label">\s*(.*?)\s*</div>\s*'
            r'<div\s+class="stat-date">\s*(.*?)\s*</div>\s*'
            r'</article>',
            re.DOTALL,
        )

        # Split by pitch type headers (h4 tags)
        # Find sections: Fastball, Changeup, Curveball, Slider
        current_pitch = "fastball"  # default first section is fastball

        # Split HTML by h4 tags to identify pitch type context
        parts = re.split(r'<h4>(.*?)</h4>', pitch_html)

        # parts[0] = before any h4 (might have fastball stats)
        # parts[1] = "Fastball", parts[2] = content after Fastball h4
        # parts[3] = "Changeup", parts[4] = content after Changeup h4, etc.

        for i, part in enumerate(parts):
            if i % 2 == 1:
                # This is a pitch type name from <h4>
                pitch_name = part.strip()
                prefix = PITCH_SECTIONS.get(pitch_name)
                if prefix:
                    current_pitch = prefix
                continue

            # This is content - extract stats
            prefix = current_pitch
            for m in stat_pattern.finditer(part):
                value = m.group(1).strip()
                label = m.group(2).strip()
                date = m.group(3).strip() or None

                if value in ("-", ""):
                    continue

                suffix = PITCH_STAT_SUFFIX.get(label)
                if suffix:
                    col_name = f"{prefix}_{suffix}"
                    # Only fill in if not already set by Selenium
                    if not stats.get(col_name):
                        stats[col_name] = self._clean_stat_value(value)
                        stats[f"{col_name}_date"] = date

    def _extract_pitching_stats(self, driver, stats: Dict):
        """Extract pitching stats via Selenium"""
        try:
            pitching_section = driver.find_element(
                By.CSS_SELECTOR, "div.bestof-chart__pitching"
            )
        except NoSuchElementException:
            return

        # Handle Fastball section (in .fastball-wrap)
        try:
            fb_wrap = pitching_section.find_element(
                By.CSS_SELECTOR, "div.fastball-wrap"
            )
            self._extract_pitch_type_stats(fb_wrap, "fastball", stats)
        except NoSuchElementException:
            pass

        # Handle other pitch types (in .stat-subgroup elements)
        try:
            subgroups = pitching_section.find_elements(
                By.CSS_SELECTOR, "div.stat-subgroup"
            )
            for subgroup in subgroups:
                try:
                    h4 = subgroup.find_element(By.TAG_NAME, "h4")
                    # .text returns uppercase ("CHANGEUP"), textContent
                    # returns title case ("Changeup") which matches PITCH_SECTIONS
                    pitch_name = h4.get_attribute("textContent").strip()
                    if not pitch_name:
                        pitch_name = h4.text.strip()
                    prefix = PITCH_SECTIONS.get(pitch_name)
                    if prefix:
                        self._extract_pitch_type_stats(subgroup, prefix, stats)
                except NoSuchElementException:
                    continue
        except Exception:
            pass

    def _extract_pitch_type_stats(
        self, container, prefix: str, stats: Dict
    ):
        """Extract stats from a pitch type container (e.g., fastball-wrap)"""
        items = container.find_elements(
            By.CSS_SELECTOR, "article.stat-item"
        )
        for item in items:
            value, label, date = self._parse_stat_item(item)
            if not label or value in ("-", "", None):
                continue

            suffix = PITCH_STAT_SUFFIX.get(label)
            if suffix:
                col_name = f"{prefix}_{suffix}"
                stats[col_name] = self._clean_stat_value(value)
                stats[f"{col_name}_date"] = date

    def _extract_section_stats(
        self, driver, section_class: str, stats: Dict
    ):
        """Extract stats from a non-pitching section using the label map"""
        try:
            section = driver.find_element(
                By.CSS_SELECTOR, f"div.{section_class}"
            )
        except NoSuchElementException:
            return

        items = section.find_elements(By.CSS_SELECTOR, "article.stat-item")
        for item in items:
            value, label, date = self._parse_stat_item(item)
            if not label or value in ("-", "", None):
                continue

            col_name = STAT_LABEL_MAP.get(label)
            if col_name:
                stats[col_name] = self._clean_stat_value(value)
                stats[f"{col_name}_date"] = date

    def _parse_stat_item(
        self, item
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Parse a single stat-item article element.
        Tries .text first, falls back to textContent attribute.
        """
        value = label = date = None

        try:
            value_el = item.find_element(By.CSS_SELECTOR, "div.stat-v")
            value = value_el.text.strip()
            if not value:
                value = value_el.get_attribute("textContent").strip()
        except NoSuchElementException:
            pass

        try:
            label_el = item.find_element(By.CSS_SELECTOR, "div.stat-label")
            label = label_el.text.strip()
            if not label:
                label = label_el.get_attribute("textContent").strip()
        except NoSuchElementException:
            pass

        try:
            date_el = item.find_element(By.CSS_SELECTOR, "div.stat-date")
            date = date_el.text.strip()
            if not date:
                date = date_el.get_attribute("textContent").strip()
            date = date or None
        except NoSuchElementException:
            pass

        return value, label, date

    @staticmethod
    def _clean_stat_value(value: str) -> Optional[str]:
        """
        Clean a stat value string.
        Ranges like "89 - 92" are kept as-is.
        Dashes mean no data.
        """
        if not value or value.strip() in ("-", ""):
            return None
        return value.strip()

    def _extract_events(self, driver) -> List[Dict[str, str]]:
        """Extract event history from the Best Of tab's event list."""
        events = []

        try:
            best_of = driver.find_element(
                By.CSS_SELECTOR,
                "div.vendor-panel__item[data-vendor='best-of']"
            )
            event_items = best_of.find_elements(
                By.CSS_SELECTOR, "div.event-item"
            )

            for item in event_items:
                try:
                    title_el = item.find_element(By.CSS_SELECTOR, "div.title")
                    date_el = item.find_element(By.CSS_SELECTOR, "div.date")
                    event = {
                        "title": title_el.text.strip(),
                        "date": date_el.text.strip(),
                    }
                    try:
                        link_el = item.find_element(
                            By.CSS_SELECTOR, "a.showcase-event"
                        )
                        event["url"] = link_el.get_attribute("href")
                    except NoSuchElementException:
                        pass
                    events.append(event)
                except NoSuchElementException:
                    continue
        except NoSuchElementException:
            pass

        return events
