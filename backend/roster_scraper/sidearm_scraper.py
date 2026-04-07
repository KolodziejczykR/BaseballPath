"""
SIDEARM Sports roster scraper for BaseballPath
Uses Selenium to render JS-heavy pages, then BeautifulSoup to parse HTML.
Handles both card-based and table-based SIDEARM themes.
"""

import os
import sys
import time
import logging
import re
from typing import List, Dict, Optional
from bs4 import BeautifulSoup

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.school_info_scraper.selenium_driver import SeleniumDriverManager

logger = logging.getLogger(__name__)


class SidearmRosterScraper:
    """Scrapes baseball rosters from SIDEARM Sports-powered athletics websites"""

    _FIELD_LABELS = [
        "Position",
        "Pos.",
        "Pos",
        "Academic Year",
        "Class",
        "Year",
        "Yr.",
        "Cl.",
        "Height",
        "Ht.",
        "Ht",
        "Weight",
        "Wt.",
        "Wt",
        "Hometown",
        "Home Town",
        "Last School",
        "High School",
        "Previous School",
        "Prev. School",
        "B/T",
        "Bats/Throws",
        "Bats",
        "Throws",
    ]

    def __init__(self, headless: bool = True, delay: float = 3.0):
        self.headless = headless
        self.delay = delay
        self.driver_manager = None

    def _ensure_driver(self):
        """Lazily initialize the Selenium driver"""
        if self.driver_manager is None:
            self.driver_manager = SeleniumDriverManager(
                headless=self.headless,
                delay=self.delay,
                timeout=30
            )

    def scrape_roster(self, roster_url: str) -> List[Dict]:
        """
        Scrape a SIDEARM Sports baseball roster page.

        Args:
            roster_url: Full URL to the roster page
                        (e.g., 'https://rolltide.com/sports/baseball/roster')

        Returns:
            List of dicts with raw player data (name, position, class_year, etc.)
            Empty list on failure.
        """
        self._ensure_driver()

        logger.info(f"Scraping roster: {roster_url}")

        if not self.driver_manager.get(roster_url, custom_delay=5):
            logger.error(f"Failed to load: {roster_url}")
            return []

        # Scroll to trigger lazy loading
        self.driver_manager.scroll_to_load_content(scroll_pause_time=1.5, max_scrolls=3)
        time.sleep(2)

        # Get rendered HTML
        try:
            html = self.driver_manager.driver.page_source
        except Exception as e:
            logger.error(f"Failed to get page source: {e}")
            return []

        soup = BeautifulSoup(html, 'html.parser')

        # Try parsing strategies in order of reliability
        players = self._parse_card_layout(soup)

        if not players:
            players = self._parse_table_layout(soup)

        if not players:
            players = self._parse_generic_table(soup)

        logger.info(f"Extracted {len(players)} players from {roster_url}")
        return players

    # ------------------------------------------------------------------
    # Strategy 1: SIDEARM card-based layout (s-person-card)
    # ------------------------------------------------------------------
    def _parse_card_layout(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse SIDEARM card-based roster layout (most common modern theme)"""

        cards = soup.select('.s-person-card')
        if not cards:
            # Try alternate container class
            cards = soup.select('.sidearm-roster-player-container')
        if not cards:
            return []

        logger.info(f"Found {len(cards)} player cards (card layout)")
        players = []

        for card in cards:
            try:
                player = self._extract_from_card(card)
                if player and player.get('name'):
                    players.append(player)
            except Exception as e:
                logger.debug(f"Error parsing card: {e}")

        return players

    def _extract_from_card(self, card) -> Optional[Dict]:
        """Extract player data from a single SIDEARM player card"""
        data = {}

        # Name: usually in h3, a link, or .s-person-details__personal-single-line
        name_el = (
            card.select_one('h3 a') or
            card.select_one('h3') or
            card.select_one('.s-person-details__personal-single-line a') or
            card.select_one('a[href*="/roster/"]')
        )
        if name_el:
            data['name'] = name_el.get_text(strip=True)

        # Jersey number from .s-stamp or similar
        number_el = card.select_one('.s-stamp') or card.select_one('.sidearm-roster-player-jersey-number')
        if number_el:
            num_text = number_el.get_text(strip=True)
            # Strip "Jersey Number" prefix if present
            num_text = re.sub(r'(?i)jersey\s*number\s*', '', num_text).strip()
            if num_text:
                data['jersey_number'] = num_text

        # Extract labeled fields from the card details.
        # SIDEARM uses both explicit labels and compact text blocks.
        card_text = self._normalize_whitespace(card.get_text(' ', strip=True))
        data.update(self._extract_labeled_fields(card))
        data.update(self._extract_compact_card_fields(card_text, data))

        return data if data.get('name') else None

    def _extract_compact_card_fields(self, card_text: str, existing: Dict) -> Dict:
        """Extract fields from unlabeled SIDEARM card text blocks."""
        if not card_text:
            return {}

        extracted: Dict[str, str] = {}

        if not existing.get("position"):
            pos_match = re.search(
                r'\b(?P<position>[A-Z]{1,4}(?:/[A-Z]{1,4}){0,2})\s+\d+\'\d{1,2}"?\s+\d{2,3}\s*lbs\b',
                card_text,
                re.IGNORECASE,
            )
            if pos_match:
                extracted["position"] = pos_match.group("position")

        if not existing.get("height"):
            ht_match = re.search(r"(?P<height>\d+'\d{1,2}\"?)", card_text)
            if ht_match:
                extracted["height"] = ht_match.group("height")

        if not existing.get("weight"):
            wt_match = re.search(r'(?P<weight>\d{2,3})\s*lbs\b', card_text, re.IGNORECASE)
            if wt_match:
                extracted["weight"] = wt_match.group("weight")

        if not existing.get("bats") or not existing.get("throws"):
            bt_match = re.search(r'\b(?P<bt>[RLSB]/[RLSB])\b', card_text)
            if bt_match:
                bats, throws = bt_match.group("bt").split("/")
                extracted.setdefault("bats", bats)
                extracted.setdefault("throws", throws)

        if not existing.get("class_year") and existing.get("name"):
            name_pattern = re.escape(existing["name"])
            year_match = re.search(
                rf'{name_pattern}\s+(?P<year>(?:R-|RS\s*)?(?:Fr|So|Jr|Sr|Gr)\.)(?:\s|$)',
                card_text,
                re.IGNORECASE,
            )
            if year_match:
                extracted["class_year"] = year_match.group("year")

        return extracted

    def _extract_labeled_fields(self, container) -> Dict:
        """
        Extract labeled fields from a SIDEARM container.
        SIDEARM often uses patterns like:
          <span class="...">Position</span> <span>INF</span>
          or inline text: "Position INF"
        """
        data = {}

        # Strategy A: Look for spans/divs with specific labels
        all_text_elements = container.find_all(['span', 'div', 'li', 'dd', 'td'])

        # Build a flat list of text segments from the container
        segments = []
        for el in all_text_elements:
            text = self._normalize_whitespace(el.get_text(" ", strip=True))
            if text:
                segments.append(text)

        # Also get the full text for regex fallback
        full_text = self._normalize_whitespace(container.get_text(' ', strip=True))

        # Position
        pos = self._find_field_value(segments, full_text,
                                     labels=['Position', 'Pos.', 'Pos'],
                                     pattern=r'(?:Position|Pos\.?)\s*[:\-]?\s*([A-Z/]+(?:\s*/\s*[A-Z]+)*)')
        if pos:
            data['position'] = pos

        # Class year / Academic year
        year = self._find_field_value(segments, full_text,
                                      labels=['Academic Year', 'Class', 'Year', 'Yr.', 'Cl.'],
                                      pattern=r'(?:Academic\s+Year|Class|Year|Yr\.?|Cl\.?)\s*[:\-]?\s*((?:R-|RS\s*)?(?:Fr|So|Jr|Sr|Gr|Freshman|Sophomore|Junior|Senior|Graduate)\.?)')
        if year:
            data['class_year'] = year

        # Height
        ht = self._find_field_value(segments, full_text,
                                    labels=['Height', 'Ht.', 'Ht'],
                                    pattern=r"(?:Height|Ht\.?)\s*[:\-]?\s*(\d[''\-]\s*\d{1,2}[\"']*)")
        if ht:
            data['height'] = ht

        # Weight
        wt = self._find_field_value(segments, full_text,
                                    labels=['Weight', 'Wt.', 'Wt'],
                                    pattern=r'(?:Weight|Wt\.?)\s*[:\-]?\s*(\d{2,3})\s*(?:lbs?\.?)?')
        if wt:
            data['weight'] = wt

        # Hometown
        ht_val = self._find_field_value(segments, full_text,
                                        labels=['Hometown', 'Home Town'],
                                        pattern=r'(?:Hometown|Home\s*Town)\s*[:\-]?\s*(.+?)(?=\s*(?:Last School|High School|Previous School|Height|Weight|Position|Academic(?:\s+Year)?|B/T|Bats|Throws|Class|Year|Yr\.?|Cl\.?)\s*[:\-]?|$)')
        if ht_val:
            data['hometown'] = ht_val.strip()

        # High school / Last school
        hs = self._find_field_value(segments, full_text,
                                    labels=['Last School', 'High School', 'Previous School', 'Prev. School'],
                                    pattern=r'(?:Last School|High School|Previous School|Prev\.\s*School)\s*[:\-]?\s*(.+?)(?=\s*(?:Hometown|Home\s*Town|Height|Weight|Position|Academic(?:\s+Year)?|B/T|Bats|Throws|Class|Year|Yr\.?|Cl\.?)\s*[:\-]?|$)')
        if hs:
            data['high_school'] = hs.strip()

        # Bats/Throws — often shown as "B/T R/R" or "R-R"
        bt = self._find_field_value(segments, full_text,
                                    labels=['B/T', 'Bats/Throws'],
                                    pattern=r'(?:B/T|Bats/Throws)\s*[:\-]?\s*([RLSB]/[RLSB])')
        if bt and '/' in bt:
            parts = bt.split('/')
            data['bats'] = parts[0].strip()
            data['throws'] = parts[1].strip()

        return data

    @staticmethod
    def _normalize_whitespace(value: str) -> str:
        return re.sub(r'\s+', ' ', value or '').strip()

    @classmethod
    def _clean_extracted_value(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return None

        cleaned = cls._normalize_whitespace(value)
        for label in sorted(cls._FIELD_LABELS, key=len, reverse=True):
            cleaned = re.sub(
                rf'^(?:{re.escape(label)}\s*[:\-]?\s*)+',
                '',
                cleaned,
                flags=re.IGNORECASE,
            )

        for label in sorted(cls._FIELD_LABELS, key=len, reverse=True):
            match = re.search(rf'\s+(?={re.escape(label)}\b)', cleaned, re.IGNORECASE)
            if match:
                cleaned = cleaned[:match.start()].strip()
                break

        cleaned = cleaned.strip(" :-")
        return cleaned or None

    @classmethod
    def _looks_like_field_label(cls, value: str) -> bool:
        normalized = cls._normalize_whitespace(value).lower().rstrip(':')
        return normalized in {label.lower().rstrip(':') for label in cls._FIELD_LABELS}

    def _find_field_value(self, segments: List[str], full_text: str,
                          labels: List[str], pattern: str) -> Optional[str]:
        """
        Find a field value using multiple strategies:
        1. Check segments for label followed by value
        2. Regex on full text
        """
        # Strategy 1: segment-based — find label segment, next segment is value
        for i, seg in enumerate(segments):
            seg_normalized = self._normalize_whitespace(seg)
            seg_lower = seg_normalized.lower().strip()
            for label in labels:
                label_lower = label.lower()
                if seg_lower == label_lower:
                    # Next segment is the value
                    if i + 1 < len(segments):
                        val = self._clean_extracted_value(segments[i + 1])
                        if val and not self._looks_like_field_label(val):
                            return val
                elif seg_lower.startswith(label_lower):
                    remainder = self._clean_extracted_value(seg_normalized[len(label):])
                    if remainder and not self._looks_like_field_label(remainder):
                        return remainder

        # Strategy 2: regex on full text
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            return self._clean_extracted_value(match.group(1))

        return None

    # ------------------------------------------------------------------
    # Strategy 2: SIDEARM table-based layout
    # ------------------------------------------------------------------
    def _parse_table_layout(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse SIDEARM table-based roster layout"""

        table = soup.select_one('table.sidearm-table') or soup.select_one('.sidearm-table')
        if not table:
            return []

        return self._parse_roster_table(table)

    # ------------------------------------------------------------------
    # Strategy 3: Generic table fallback
    # ------------------------------------------------------------------
    def _parse_generic_table(self, soup: BeautifulSoup) -> List[Dict]:
        """
        Fallback: find any table whose headers suggest it's a roster table,
        then parse its rows.
        """
        roster_headers = {'name', 'pos', 'position', 'yr', 'year', 'cl', 'class',
                          'ht', 'height', 'wt', 'weight'}

        tables = soup.find_all('table')
        for table in tables:
            headers = self._get_table_headers(table)
            header_set = {h.lower().rstrip('.') for h in headers}

            # Must have at least name + one of position/year
            if 'name' in header_set and header_set & {'pos', 'position', 'yr', 'year', 'cl', 'class'}:
                logger.info(f"Found roster table with headers: {headers}")
                return self._parse_roster_table(table, headers)

        return []

    def _get_table_headers(self, table) -> List[str]:
        """Extract header texts from a table"""
        headers = []
        header_row = table.select_one('thead tr') or table.select_one('tr')
        if header_row:
            for th in header_row.find_all(['th', 'td']):
                headers.append(th.get_text(strip=True))
        return headers

    def _parse_roster_table(self, table, headers: List[str] = None) -> List[Dict]:
        """Parse a roster table given its headers"""
        if headers is None:
            headers = self._get_table_headers(table)

        if not headers:
            return []

        # Normalize headers for column mapping
        col_map = self._build_column_map(headers)

        players = []
        rows = table.select('tbody tr') or table.select('tr')[1:]  # skip header row

        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 2:
                continue

            player = {}
            cell_texts = [c.get_text(strip=True) for c in cells]

            # Also check for links in name column for the actual name
            name_idx = col_map.get('name')
            if name_idx is not None and name_idx < len(cells):
                name_link = cells[name_idx].select_one('a')
                player['name'] = name_link.get_text(strip=True) if name_link else cell_texts[name_idx]

            for field, idx in col_map.items():
                if field == 'name':
                    continue  # already handled above
                if idx < len(cell_texts):
                    val = cell_texts[idx]
                    if val:
                        player[field] = val

            if player.get('name'):
                players.append(player)

        return players

    def _build_column_map(self, headers: List[str]) -> Dict[str, int]:
        """Map normalized field names to column indices"""
        mapping = {}
        header_aliases = {
            'name': ['name', 'player', 'student-athlete'],
            'jersey_number': ['#', 'no', 'no.', 'number', 'jersey'],
            'position': ['pos', 'pos.', 'position'],
            'class_year': ['yr', 'yr.', 'year', 'cl', 'cl.', 'class', 'academic year', 'elig'],
            'height': ['ht', 'ht.', 'height'],
            'weight': ['wt', 'wt.', 'weight'],
            'bats_throws': ['b/t', 'b-t', 'bats/throws'],
            'hometown': ['hometown', 'home town', 'city/state'],
            'high_school': ['high school', 'last school', 'previous school', 'prev. school', 'school'],
            'bats': ['bats', 'bat'],
            'throws': ['throws', 'throw'],
        }

        for i, header in enumerate(headers):
            h = header.lower().strip()
            for field, aliases in header_aliases.items():
                if h in aliases:
                    mapping[field] = i
                    break

        return mapping

    def close(self):
        """Close the Selenium driver"""
        if self.driver_manager:
            self.driver_manager.close()
            self.driver_manager = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
