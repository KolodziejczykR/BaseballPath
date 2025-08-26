"""
Niche.com Beautiful Soup Scraper for BaseballPATH
Alternative to Selenium scraper to avoid bot detection
Uses requests + BeautifulSoup instead of browser automation
"""

import os
import sys
import time
import re
import random
import requests
from typing import Dict, List
from dataclasses import dataclass, asdict
from bs4 import BeautifulSoup
from lxml import html
from dotenv import load_dotenv

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.scraper.selenium_driver import normalize_text, is_valid_grade
from backend.scraper.niche_xpaths import (
    CATEGORY_GRADE_MAPPING,
    ENROLLMENT_XPATH
)

from backend.utils.scraping_types import NicheRatings

load_dotenv()

class NicheBSScraper:
    """Niche.com scraper using requests and lxml"""
    
    def __init__(self, delay: float = 2.0):
        """
        Initialize with requests session and realistic headers
        
        Args:
            delay: Delay between requests in seconds
        """
        self.delay = delay
        self.base_url = "https://www.niche.com/colleges"
        self.session = requests.Session()
        
        # Randomize user agents to avoid detection
        self.user_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15"
        ]
        
        # Setup realistic headers to avoid detection
        self._update_headers()
        
        # Add session warmup
        self._session_warmed = False
    
    def _update_headers(self):
        """Update headers with randomized values"""
        self.session.headers.clear()
        self.session.headers.update({
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': random.choice(['en-US,en;q=0.9', 'en-US,en;q=0.8,es;q=0.7']),
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        })
    
    def _warm_up_session(self):
        """Warm up the session by visiting the main page first"""
        try:
            # Random delay before starting
            time.sleep(random.uniform(2, 4))
            
            # Refresh headers for warmup
            self._update_headers()
            
            # Visit main page first to establish cookies and session
            main_response = self.session.get('https://www.niche.com/', timeout=20)
            if main_response.status_code == 200:
                # Random delay to mimic human behavior
                time.sleep(random.uniform(3, 6))
                
                # Update headers again for colleges page
                self._update_headers()
                self.session.headers['Referer'] = 'https://www.niche.com/'
                
                # Visit colleges search page
                search_response = self.session.get('https://www.niche.com/colleges/search/best-colleges/', timeout=20)
                if search_response.status_code == 200:
                    time.sleep(random.uniform(2, 4))
                    self._session_warmed = True
        except Exception:
            # If warmup fails, continue anyway
            self._session_warmed = True
    
    def scrape_school_ratings(self, school_name: str, custom_url: str = None) -> NicheRatings:
        """
        Scrape comprehensive Niche.com ratings for a school using BeautifulSoup
        
        Args:
            school_name: Official school name
            custom_url: Optional custom Niche URL if known
            
        Returns:
            NicheRatings object with all available data
        """
        try:
            # Build Niche URL
            niche_url = custom_url or self._build_niche_url(school_name)
            
            # Warm up session if needed
            if not self._session_warmed:
                self._warm_up_session()
            
            # Update headers for this specific request
            self._update_headers()
            self.session.headers['Referer'] = 'https://www.niche.com/colleges/search/best-colleges/'
            
            # Random delay before actual request
            time.sleep(random.uniform(3, 7))
            
            # Make request with session
            response = self.session.get(niche_url, timeout=30)
            if response.status_code != 200:
                return NicheRatings(school_name=school_name, niche_url=niche_url,
                                  error=f"HTTP {response.status_code}")
            
            # Check for bot detection
            if "access to this page has been denied" in response.text.lower():
                return NicheRatings(school_name=school_name, niche_url=niche_url,
                                  error="Bot detection - access denied")
            
            if "press & hold to confirm" in response.text.lower():
                return NicheRatings(school_name=school_name, niche_url=niche_url,
                                  error="CAPTCHA detected")
            
            # Parse with lxml for XPath support
            tree = html.fromstring(response.text)
            
            # Initialize ratings object
            ratings = NicheRatings(school_name=school_name, niche_url=niche_url)
            
            # Extract data using XPaths with lxml
            self._extract_category_grades(tree, ratings)  # This now includes overall grade
            self._extract_school_stats(tree, ratings)
            
            # Validate extracted data
            self._validate_extracted_data(ratings)
            
            return ratings
            
        except Exception as e:
            return NicheRatings(school_name=school_name, error=str(e))
        
        finally:
            # Rate limiting with randomization
            time.sleep(self.delay + random.uniform(1, 3))
    
    
    def _build_niche_url(self, school_name: str) -> str:
        """Build Niche URL from school name"""
        url_name = school_name.lower().strip()
        
        # Common replacements (order matters)
        replacements = [
            ('university of ', 'university-of-'),
            ('college of ', 'college-of-'), 
            (' institute of technology', '-institute-of-technology'),
            (' tech', '-institute-of-technology'),
            ('st. ', 'saint-'),
            (' & ', '-and-'),
            (' and ', '-and-'),
            (' at ', '-'),
            (' university', '-university'),
            (' college', '-college'),
            (' - ', '-'),
            (' ', '-')
        ]
        
        for old, new in replacements:
            url_name = url_name.replace(old, new)
        
        # Clean up multiple dashes and special characters
        url_name = re.sub(r'[^a-z0-9-]', '', url_name)
        url_name = re.sub(r'-+', '-', url_name).strip('-')
        
        return f"{self.base_url}/{url_name}/"
    
    
    def _extract_category_grades(self, tree, ratings: NicheRatings):
        """Extract category grades using class-based approach"""
        # Find all section grades and map them to categories
        section_grades = tree.xpath("//div[contains(@class, 'niche__grade--section')]")
        
        # Extract all section grades and assign them based on their position in the document
        for i, element in enumerate(section_grades):
            if i + 1 in CATEGORY_GRADE_MAPPING:
                rating_field = CATEGORY_GRADE_MAPPING[i + 1]
                
                grade_text = element.text_content().strip()
                # Remove 'grade' prefix if present
                clean_grade = grade_text.replace('grade', '').strip()
                
                # Convert "A minus" to "A-", "B plus" to "B+", etc.
                clean_grade = clean_grade.replace(' minus', '-').replace(' plus', '+')
                
                # Accept 'unavailable' as a valid grade value
                if is_valid_grade(clean_grade) or clean_grade.lower() == 'unavailable':
                    setattr(ratings, rating_field, clean_grade)
    
    def _extract_school_stats(self, tree, ratings: NicheRatings):
        """Extract school statistics using DOM-like navigation"""
        # Only extract enrollment
        self._extract_enrollment_dom_style(tree, ratings)
    
    def _extract_enrollment_dom_style(self, tree, ratings: NicheRatings):
        """Extract enrollment using pattern search"""
        try:
            # Use the advanced approach with .lastChild.data suffix
            enrollment_xpath = ENROLLMENT_XPATH + ".lastChild.data"
            enrollment_text = self._fetch_text_by_xpath_advanced(ratings.niche_url, enrollment_xpath)
            
            if enrollment_text:
                ratings.enrollment = normalize_text(enrollment_text)
        except Exception:
            pass
            
        # Fallback: try pattern search for enrollment
        if not ratings.enrollment:
            self._try_enrollment_pattern_search(tree, ratings)
    
    
    def _try_enrollment_pattern_search(self, tree, ratings: NicheRatings):
        """Fallback pattern search for enrollment"""
        try:
            # Get all text content
            full_text = tree.text_content()
            
            # Look for enrollment patterns
            import re
            patterns = [
                r'enrollment[:\s]*(\d{1,3}(?:,\d{3})*)',
                r'(\d{1,3}(?:,\d{3})*)\s*(?:undergraduate\s*)?students?',
                r'(\d{1,3}(?:,\d{3})*)\s*undergrad',
                r'student body[:\s]*(\d{1,3}(?:,\d{3})*)',
            ]
            
            for pattern in patterns:
                matches = re.finditer(pattern, full_text.lower())
                for match in matches:
                    enrollment = match.group(1)
                    ratings.enrollment = enrollment
                    return
        except Exception:
            pass
    
    
    def _fetch_text_by_xpath_advanced(self, url: str, xpath: str, timeout: int = 20) -> str:
        """
        Fetch text content from `url` at the node specified by `xpath`.
        Supports a suffix '.lastChild.data' to return the last text node under the element.
        Falls back to BeautifulSoup with a basic XPath->CSS conversion for simple absolute paths.
        """
        import re
        from bs4 import NavigableString
        
        want_last = False
        if xpath.endswith(".lastChild.data"):
            want_last = True
            xpath = xpath[: -len(".lastChild.data")]

        # Fix common mistake: XPath is 1-based; coerce [0] -> [1]
        xpath = re.sub(r"\[(?:0)\]", "[1]", xpath)

        # Use existing session instead of new request
        response = self.session.get(url, timeout=timeout)
        response.raise_for_status()
        content = response.text

        # --- 1) Try real XPath with lxml (best for your exact path) ---
        try:
            doc = html.fromstring(content)
            nodes = doc.xpath(xpath)
            if nodes:
                node = nodes[0]
                if want_last:
                    texts = [t.strip() for t in node.xpath(".//text()") if t.strip()]
                    return texts[-1] if texts else ""
                # full text under the node, normalized
                return " ".join(" ".join(node.xpath(".//text()")).split())
        except Exception:
            pass  # fall through to BeautifulSoup

        # --- 2) Fallback: convert simple absolute XPath -> CSS and use BeautifulSoup ---
        css = self._xpath_to_css_simple(xpath)
        soup = BeautifulSoup(content, "html.parser")
        el = soup.select_one(css) if css else None
        if not el:
            raise ValueError(f"Element not found via XPath or CSS.\nXPath: {xpath}\nCSS: {css}")

        if want_last:
            last = ""
            for d in el.descendants:
                if isinstance(d, NavigableString):
                    s = d.strip()
                    if s:
                        last = s
            return last
        else:
            return el.get_text(strip=True)

    def _xpath_to_css_simple(self, xpath: str) -> str:
        """
        Convert *simple absolute* XPaths like /html/body/div[1]/span[2]
        into CSS: html > body > div:nth-of-type(1) > span:nth-of-type(2)
        (No support for predicates/attributes/functions beyond [n].)
        """
        import re
        
        if not xpath.startswith("/"):
            return None
        parts = [p for p in xpath.split("/") if p]
        css_parts = []
        for p in parts:
            m = re.fullmatch(r"([a-zA-Z][\w-]*)(\[(\d+)\])?", p)
            if not m:
                return None
            tag, _, idx = m.groups()
            if idx is None:
                css_parts.append(tag)
            else:
                n = max(1, int(idx))  # coerce 0->1 just in case
                css_parts.append(f"{tag}:nth-of-type({n})")
        return " > ".join(css_parts)
    
    
    
    
    def _validate_extracted_data(self, ratings: NicheRatings):
        """Validate extracted data for reasonableness"""
        # Check enrollment
        if ratings.enrollment:
            try:
                enrollment_num = int(ratings.enrollment.replace(',', ''))
                if not (100 <= enrollment_num <= 100000):
                    ratings.enrollment = None
            except:
                ratings.enrollment = None
        
        # Check grades
        grade_fields = ['overall_grade', 'academics_grade', 'campus_life_grade', 
                       'athletics_grade', 'value_grade', 'student_life_grade',
                       'party_scene_grade', 'diversity_grade', 'location_grade', 'safety_grade',
                       'professors_grade', 'dorms_grade', 'campus_food_grade']
        
        for field in grade_fields:
            grade = getattr(ratings, field, None)
            if grade and not (is_valid_grade(grade) or grade.lower() == 'unavailable'):
                setattr(ratings, field, None)
    
    def scrape_multiple_schools(self, school_names: List[str]) -> Dict[str, NicheRatings]:
        """
        Scrape ratings for multiple schools using BeautifulSoup
        
        Args:
            school_names: List of school names to scrape
            
        Returns:
            Dictionary mapping school names to NicheRatings objects
        """
        results = {}
        
        for i, school_name in enumerate(school_names):
            ratings = self.scrape_school_ratings(school_name)
            results[school_name] = ratings
            
            # Rate limiting between requests
            if i < len(school_names) - 1:
                time.sleep(self.delay)
        
        return results

def main():
    """Test the BeautifulSoup Niche scraper"""
    test_schools = [
        "Union College",
        "University of Illinois at Urbana-Champaign",
        "University of Michigan",
    ]
    scraper = NicheBSScraper(delay=5.0)  # Increased delay
    
    results = scraper.scrape_multiple_schools(test_schools)
    
    # Print results
    for school_name, ratings in results.items():
        print(f"\n{school_name}:")
        print(f"  Overall: {ratings.overall_grade}")
        print(f"  Academics: {ratings.academics_grade}")
        print(f"  Campus Life: {ratings.campus_life_grade}")
        print(f"  Athletics: {ratings.athletics_grade}")
        print(f"  Value: {ratings.value_grade}")
        print(f"  Student Life: {ratings.student_life_grade}")
        print(f"  Party Scene: {ratings.party_scene_grade}")
        print(f"  Diversity: {ratings.diversity_grade}")
        print(f"  Location: {ratings.location_grade}")
        print(f"  Professors: {ratings.professors_grade}")
        print(f"  Dorms: {ratings.dorms_grade}")
        print(f"  Campus Food: {ratings.campus_food_grade}")
        print(f"  Safety: {ratings.safety_grade}")
        print(f"  Enrollment: {ratings.enrollment}")
        print(f"  Error: {ratings.error}")

if __name__ == "__main__":
    main()