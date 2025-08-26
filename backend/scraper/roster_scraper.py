"""
College Baseball Roster Scraper for BaseballPATH
Specialized scraper for baseball roster data from athletics websites
"""

import os
import sys
import time
import re
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, asdict
from selenium.webdriver.common.by import By
from dotenv import load_dotenv

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.scraper.selenium_driver import SeleniumDriverManager, normalize_text

load_dotenv()

@dataclass
class RosterData:
    """Data class for baseball roster information"""
    school_name: str
    position_counts: Dict[str, Dict[str, int]] = None  # {'SS': {'FR': 1, 'SO': 2, ...}}
    total_players: int = 0
    roster_url: str = None
    coaching_staff: List[str] = None
    conference: str = None
    division: str = None
    season_year: str = None
    last_updated: str = None
    error: str = None
    
    def __post_init__(self):
        if self.position_counts is None:
            self.position_counts = {}
        if self.coaching_staff is None:
            self.coaching_staff = []
    
    def get_position_summary(self, position: str) -> Dict[str, int]:
        """Get class year breakdown for a specific position"""
        return self.position_counts.get(position, {'FR': 0, 'SO': 0, 'JR': 0, 'SR': 0, 'GR': 0})
    
    def get_total_at_position(self, position: str) -> int:
        """Get total number of players at a position"""
        return sum(self.get_position_summary(position).values())
    
    def get_underclassmen_at_position(self, position: str) -> int:
        """Get number of FR/SO at a position (blocks future playing time)"""
        summary = self.get_position_summary(position)
        return summary.get('FR', 0) + summary.get('SO', 0)
    
    def get_upperclassmen_at_position(self, position: str) -> int:
        """Get number of JR/SR/GR at a position (graduation opportunities)"""
        summary = self.get_position_summary(position)
        return summary.get('JR', 0) + summary.get('SR', 0) + summary.get('GR', 0)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)

class RosterScraper:
    """Specialized scraper for college baseball roster data"""
    
    def __init__(self, driver_manager: SeleniumDriverManager):
        """
        Initialize with existing WebDriver manager
        
        Args:
            driver_manager: Configured SeleniumDriverManager instance
        """
        self.driver_manager = driver_manager
        
        # Common athletics domain patterns
        self.athletics_patterns = [
            "{school}sports.com",
            "{school}athletics.com", 
            "{school}.edu/athletics",
            "go{school}.com",
            "{school}tigers.com",
            "{school}bulldogs.com"
        ]
    
    def scrape_roster_data(self, school_name: str, athletics_domain: str = None, 
                          roster_url: str = None) -> RosterData:
        """
        Scrape baseball roster data for a school
        
        Args:
            school_name: Official school name
            athletics_domain: Known athletics domain (e.g., "georgiadogs.com")
            roster_url: Direct roster URL if known
            
        Returns:
            RosterData object with roster analysis
        """
        print(f"Scraping roster data for: {school_name}")
        
        try:
            roster_data = RosterData(school_name=school_name)
            
            # Try direct roster URL first
            if roster_url:
                if self._scrape_roster_from_url(roster_url, roster_data):
                    return roster_data
            
            # Try to find athletics domain and roster URLs
            if not athletics_domain:
                athletics_domain = self._find_athletics_domain(school_name)
            
            if not athletics_domain:
                return RosterData(school_name=school_name, 
                                error="Could not find athletics website")
            
            # Try common roster URL patterns
            roster_urls = self._generate_roster_urls(athletics_domain)
            
            for url in roster_urls:
                if self._scrape_roster_from_url(url, roster_data):
                    break
            else:
                roster_data.error = "Could not find valid roster page"
            
            return roster_data
            
        except Exception as e:
            print(f"Error scraping roster for {school_name}: {e}")
            return RosterData(school_name=school_name, error=str(e))
    
    def _scrape_roster_from_url(self, url: str, roster_data: RosterData) -> bool:
        """
        Attempt to scrape roster from a specific URL
        
        Args:
            url: Roster URL to try
            roster_data: RosterData object to populate
            
        Returns:
            bool: Success status
        """
        try:
            print(f"Trying roster URL: {url}")
            
            if not self.driver_manager.get(url, custom_delay=3.0):
                return False
            
            # Verify this is a baseball roster page
            if not self._verify_roster_page():
                return False
            
            roster_data.roster_url = url
            
            # Extract roster information
            self._extract_player_data(roster_data)
            self._extract_coaching_staff(roster_data)
            self._extract_team_info(roster_data)
            
            # Consider successful if we found at least some players
            return roster_data.total_players > 0
            
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return False
    
    def _verify_roster_page(self) -> bool:
        """Verify current page is a baseball roster"""
        title = self.driver_manager.get_page_title().lower()
        keywords = ['baseball', 'roster', 'team', 'players']
        
        # Check title and page content
        title_match = any(keyword in title for keyword in keywords)
        content_match = self.driver_manager.page_contains_keywords(['baseball', 'roster'])
        
        return title_match or content_match
    
    def _extract_player_data(self, roster_data: RosterData):
        """Extract player position and class year data"""
        
        # Common player row selectors
        player_selectors = [
            ".roster-player",
            ".player-row", 
            ".athlete-row",
            "tbody tr",
            ".roster tbody tr",
            "[data-player-id]"
        ]
        
        players = []
        for selector in player_selectors:
            players = self.driver_manager.find_elements_safe(selector)
            if players:
                break
        
        if not players:
            print("No player elements found")
            return
        
        position_counts = {}
        valid_players = 0
        
        for player_element in players:
            try:
                # Extract position
                position = self._extract_player_position(player_element)
                if not position:
                    continue
                
                # Extract class year
                class_year = self._extract_player_class(player_element)
                if not class_year:
                    continue
                
                # Normalize values
                position = self._normalize_position(position)
                class_year = self._normalize_class_year(class_year)
                
                # Update counts
                if position not in position_counts:
                    position_counts[position] = {'FR': 0, 'SO': 0, 'JR': 0, 'SR': 0, 'GR': 0}
                
                if class_year in position_counts[position]:
                    position_counts[position][class_year] += 1
                    valid_players += 1
                
            except Exception as e:
                continue  # Skip problematic player entries
        
        roster_data.position_counts = position_counts
        roster_data.total_players = valid_players
    
    def _extract_player_position(self, player_element) -> Optional[str]:
        """Extract position from player row"""
        position_selectors = [
            ".position", ".pos", 
            "td:nth-child(3)", "td:nth-child(4)", 
            ".player-position",
            "[data-position]"
        ]
        
        for selector in position_selectors:
            elements = player_element.find_elements(By.CSS_SELECTOR, selector)
            for element in elements:
                text = self.driver_manager.extract_text_safe(element)
                if text and len(text) <= 10:  # Reasonable position length
                    return text
        
        return None
    
    def _extract_player_class(self, player_element) -> Optional[str]:
        """Extract class year from player row"""
        class_selectors = [
            ".class", ".year", ".cl", 
            "td:nth-child(2)", "td:nth-child(1)",
            ".player-class", ".player-year",
            "[data-class]"
        ]
        
        for selector in class_selectors:
            elements = player_element.find_elements(By.CSS_SELECTOR, selector)
            for element in elements:
                text = self.driver_manager.extract_text_safe(element)
                if text and len(text) <= 10:  # Reasonable class length
                    return text
        
        return None
    
    def _extract_coaching_staff(self, roster_data: RosterData):
        """Extract coaching staff information"""
        coaching_selectors = [
            ".coaching-staff .coach-name",
            ".coach", 
            ".staff-member",
            "[data-coach]"
        ]
        
        coaches = []
        for selector in coaching_selectors:
            elements = self.driver_manager.find_elements_safe(selector)
            for element in elements[:5]:  # Limit to reasonable number
                coach_name = self.driver_manager.extract_text_safe(element)
                if coach_name and len(coach_name.split()) >= 2:  # At least first/last name
                    coaches.append(coach_name)
        
        roster_data.coaching_staff = coaches
    
    def _extract_team_info(self, roster_data: RosterData):
        """Extract team/conference information"""
        
        # Conference information
        conference_selectors = [
            ".conference", ".league", 
            "[data-conference]",
            ".team-info .conference"
        ]
        
        for selector in conference_selectors:
            element, found = self.driver_manager.find_element_safe(selector, timeout=3)
            if found:
                conference = self.driver_manager.extract_text_safe(element)
                if conference:
                    roster_data.conference = conference
                    break
        
        # Season year
        year_match = re.search(r'20\d{2}', self.driver_manager.get_page_title())
        if year_match:
            roster_data.season_year = year_match.group()
    
    def _generate_roster_urls(self, athletics_domain: str) -> List[str]:
        """Generate possible roster URLs for an athletics domain"""
        base_urls = [
            f"https://{athletics_domain}",
            f"https://www.{athletics_domain}"
        ]
        
        roster_paths = [
            "/sports/baseball/roster",
            "/sports/mens-baseball/roster", 
            "/sports/baseball/team",
            "/baseball/roster",
            "/baseball/team",
            "/sports/baseball",
            "/roster/baseball"
        ]
        
        urls = []
        for base in base_urls:
            for path in roster_paths:
                urls.append(f"{base}{path}")
        
        return urls
    
    def _find_athletics_domain(self, school_name: str) -> Optional[str]:
        """
        Try to determine athletics domain for a school
        This is a simplified version - could be enhanced with web search
        """
        # Common patterns based on school name
        school_short = re.sub(r'\b(university|college)\b', '', school_name.lower()).strip()
        school_short = re.sub(r'\bof\b', '', school_short).strip()
        school_short = school_short.replace(' ', '')
        
        # Known athletics domains (could be expanded)
        known_domains = {
            'georgia': 'georgiadogs.com',
            'georgiatech': 'ramblinwreck.com',
            'alabam': 'rolltide.com',
            'auburn': 'auburntigers.com'
        }
        
        for key, domain in known_domains.items():
            if key in school_short:
                return domain
        
        return None
    
    def _normalize_position(self, position: str) -> str:
        """Normalize position names to standard abbreviations"""
        position = position.upper().strip()
        
        position_map = {
            'CATCHER': 'C', 'CATCH': 'C', 'CA': 'C',
            'FIRST BASE': '1B', 'FIRST': '1B', '1ST': '1B', '1B/DH': '1B',
            'SECOND BASE': '2B', 'SECOND': '2B', '2ND': '2B',
            'THIRD BASE': '3B', 'THIRD': '3B', '3RD': '3B',
            'SHORTSTOP': 'SS', 'SHORT': 'SS', 'SS/2B': 'SS',
            'OUTFIELD': 'OF', 'OUTFIELDER': 'OF', 'LEFT FIELD': 'OF', 
            'CENTER FIELD': 'OF', 'RIGHT FIELD': 'OF', 'LF': 'OF', 'CF': 'OF', 'RF': 'OF',
            'PITCHER': 'P', 'PITCH': 'P', 'RHP': 'P', 'LHP': 'P',
            'DESIGNATED HITTER': 'DH', 'DH': 'DH',
            'INFIELD': 'IF', 'INFIELDER': 'IF', 'UTILITY': 'UT'
        }
        
        return position_map.get(position, position)
    
    def _normalize_class_year(self, class_year: str) -> str:
        """Normalize class year to standard abbreviations"""
        class_year = class_year.upper().strip()
        
        class_map = {
            'FRESHMAN': 'FR', 'FRESH': 'FR', 'FR.': 'FR', '1ST': 'FR',
            'SOPHOMORE': 'SO', 'SOPH': 'SO', 'SO.': 'SO', '2ND': 'SO',
            'JUNIOR': 'JR', 'JR.': 'JR', '3RD': 'JR',
            'SENIOR': 'SR', 'SR.': 'SR', '4TH': 'SR',
            'GRADUATE': 'GR', 'GRAD': 'GR', 'GR.': 'GR', '5TH': 'GR'
        }
        
        return class_map.get(class_year, class_year)
    
    def scrape_multiple_schools(self, school_list: List[str], 
                               known_domains: Dict[str, str] = None) -> Dict[str, RosterData]:
        """
        Scrape roster data for multiple schools
        
        Args:
            school_list: List of school names
            known_domains: Optional mapping of school names to athletics domains
            
        Returns:
            Dictionary mapping school names to RosterData objects
        """
        known_domains = known_domains or {}
        results = {}
        
        for i, school_name in enumerate(school_list):
            print(f"\n--- Roster scraping {i+1}/{len(school_list)}: {school_name} ---")
            
            athletics_domain = known_domains.get(school_name)
            roster_data = self.scrape_roster_data(school_name, athletics_domain)
            results[school_name] = roster_data
            
            # Rate limiting
            if i < len(school_list) - 1:
                time.sleep(self.driver_manager.delay)
        
        return results

def main():
    """Test the roster scraper"""
    test_schools = ["University of Georgia", "Georgia Tech"]
    
    with SeleniumDriverManager(headless=True, delay=3.0) as driver_manager:
        scraper = RosterScraper(driver_manager)
        
        results = scraper.scrape_multiple_schools(test_schools)
        
        # Print results
        for school_name, roster_data in results.items():
            print(f"\n{school_name}:")
            print(f"  Total Players: {roster_data.total_players}")
            print(f"  SS Players: {roster_data.get_total_at_position('SS')}")
            print(f"  Conference: {roster_data.conference}")
            print(f"  Error: {roster_data.error}")

if __name__ == "__main__":
    main()