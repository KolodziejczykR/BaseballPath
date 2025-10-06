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
from bs4 import BeautifulSoup
from lxml import html
from dotenv import load_dotenv

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.school_info_scraper.selenium_driver import normalize_text, is_valid_grade
from backend.utils.niche_xpaths import (
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
            
            # Random delay before actual request (increased range)
            time.sleep(random.uniform(4, 9))
            
            # Make request with session
            response = self.session.get(niche_url, timeout=30)
            
            # If initial request fails, try fallback URL with simplified name
            if response.status_code != 200:
                fallback_url = self._get_fallback_general_url(niche_url)
                if fallback_url and fallback_url != niche_url:
                    print(f"    🔄 Initial URL failed, trying fallback: {fallback_url}")
                    time.sleep(random.uniform(2, 4))  # Brief delay before retry
                    response = self.session.get(fallback_url, timeout=30)
                    if response.status_code == 200:
                        niche_url = fallback_url  # Update URL for success logging
                    else:
                        return NicheRatings(school_name=school_name, niche_url=niche_url,
                                          error=f"HTTP {response.status_code} (tried fallback)")
                else:
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
    
    def scrape_multiple_schools(self, school_names: List[str]) -> Dict[str, NicheRatings]:
        """
        Scrape Niche ratings for multiple schools with enhanced bot detection avoidance
        
        Args:
            school_names: List of school names to scrape
            
        Returns:
            Dictionary mapping school_name -> NicheRatings
        """
        results = {}
        
        print(f"  Starting Niche scraping for {len(school_names)} schools with {self.delay}s base delay...")
        
        # Warm up session once for all requests
        if not getattr(self, '_session_warmed', False):
            self._warm_up_session()
        
        total_schools = len(school_names)
        for i, school_name in enumerate(school_names):
            print(f"  Scraping Niche data for {school_name} ({i+1}/{total_schools})")
            
            # Progressive delay based on percentage of schools scraped (not total count)
            progress_percent = i / total_schools if total_schools > 0 else 0
            current_delay = self.delay
            
            if progress_percent >= 0.33:  # 33% through - increase delay
                current_delay = self.delay * 1.5
                if i == int(total_schools * 0.33):  # First time hitting 33%
                    print(f"    📈 33% complete - increasing delays (1.5x)")
            
            if progress_percent >= 0.50:  # 50% through - increase delay more
                current_delay = self.delay * 2
                if i == int(total_schools * 0.50):  # First time hitting 50%
                    print(f"    📈 50% complete - increasing delays (2.5x)")
            
            if progress_percent >= 0.75:  # 75% through - max delay
                current_delay = self.delay * 3
                if i == int(total_schools * 0.75):  # First time hitting 75%
                    print(f"    📈 75% complete - maximum delays (4x)")
            
            # Add extra cooldown every 33% or every 10 requests, whichever is smaller
            cooldown_interval = min(10, max(3, total_schools // 3))
            if i > 0 and i % cooldown_interval == 0:
                cooldown_delay = random.uniform(15, 25)  # 15-25 second cooldown
                print(f"    🧊 Cooldown break: waiting {cooldown_delay:.1f}s...")
                time.sleep(cooldown_delay)
            
            # Random delay before each request
            random_delay = random.uniform(current_delay, current_delay + 3)
            if i > 0:  # No delay for first school
                print(f"    Waiting {random_delay:.1f}s to avoid bot detection...")
                time.sleep(random_delay)
            
            # Refresh headers periodically
            header_refresh_interval = min(5, max(4, total_schools // 4))
            if i > 0 and i % header_refresh_interval == 0:
                print(f"    🔄 Refreshing session headers...")
                self._update_headers()
            
            # Scrape this school
            ratings = self.scrape_school_ratings(school_name)
            results[school_name] = ratings
            
            # Check if we got blocked and respond appropriately
            if ratings.error:
                error_msg = ratings.error.lower()
                if "bot detection" in error_msg or "access denied" in error_msg or "captcha" in error_msg:
                    print(f"    🚫 Bot detection encountered at school {i+1}. Implementing countermeasures...")
                    
                    # Increase base delay more aggressively
                    self.delay = min(self.delay * 2.0, 20.0)  # Cap at 20 seconds
                    
                    # Take a longer break immediately
                    emergency_delay = random.uniform(30, 60)
                    print(f"    ⏸️ Emergency cooldown: waiting {emergency_delay:.1f}s...")
                    time.sleep(emergency_delay)
                    
                    # Refresh headers to simulate new browser
                    self._update_headers()
                    
                else:
                    print(f"    ❌ Error for {school_name}: {ratings.error}")
            elif ratings.overall_grade:
                print(f"    ✅ Successfully scraped {school_name}")
            else:
                print(f"    ⚠️ Incomplete data for {school_name} (possible soft blocking)")
                
                # Soft blocking - increase delays slightly
                if not ratings.overall_grade and not ratings.error:
                    self.delay = min(self.delay * 1.2, 15.0)
        
        successful_scrapes = sum(1 for r in results.values() if r.overall_grade and not r.error)
        print(f"  📊 Completed Niche scraping: {successful_scrapes}/{len(school_names)} successful")
        
        return results
    
    
    def _build_niche_url(self, school_name: str) -> str:
        """Build Niche URL from school name"""
        
        # Check if school name is in the predefined mapping first
        school_map_d1 = {
            'Texas Tech University': 'texas-tech-university',
            'Texas A & M University-College Station': 'texas-a-and-m-university',
            'University at Albany': 'university-at-albany-suny',
            'The University of Texas at Austin': 'university-of-texas-austin',
            'Louisiana State University and Agricultural & Mechanical College': 'louisiana-state-university',
            'University of Pittsburgh-Pittsburgh Campus': 'university-of-pittsburgh',
            'University of Missouri-Columbia': 'university-of-missouri',
            'The University of Tennessee-Knoxville': 'university-of-tennessee',
            'University of North Carolina at Chapel Hill': 'university-of-north-carolina-at-chapel-hill',
            'Virginia Polytechnic Institute and State University': 'virginia-tech',
            'University of Oklahoma-Norman Campus': 'university-of-oklahoma',
            'The University of Texas at El Paso': 'university-of-texas-el-paso',
            "Missouri State University-Springfield": 'missouri-state-university',
            "University of Hawaii at Manoa": 'university-of-hawaii-at-manoa',
            'University of Nebraska at Omaha': 'university-of-nebraska-at-omaha',
            "The University of Texas at San Antonio": 'the-university-of-texas-at-san-antonio',
            "Pennsylvania State University-Main Campus": 'penn-state',
            "University of North Carolina at Charlotte": 'university-of-north-carolina-at-charlotte',
            "Mount St. Mary's University": 'mount-st-marys-university',
            "California Polytechnic State University-San Luis Obispo": "cal-poly-san-luis-obispo",
            "University of South Carolina-Columbia": "university-of-south-carolina",
            "The University of Texas at Arlington": "university-of-texas-arlington",
            "The University of Tennessee-Martin": "university-of-tennessee-at-martin",
        }
        
        # If school name is in the mapping, use the predefined simplified name
        if school_name in school_map_d1:
            return f"{self.base_url}/{school_map_d1[school_name]}/"
        
        # Otherwise, use the standard URL generation logic
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
            (' ', '-'),
        ]
        
        for old, new in replacements:
            url_name = url_name.replace(old, new)
        
        # Clean up multiple dashes and special characters
        url_name = re.sub(r'[^a-z0-9-]', '', url_name)
        url_name = re.sub(r'-+', '-', url_name).strip('-')
        
        # Remove '-main-campus' if present (keep everything before it)
        if '-main-campus' in url_name:
            url_name = url_name.split('-main-campus')[0]
        
        return f"{self.base_url}/{url_name}/"
    
    def _get_fallback_general_url(self, original_url: str) -> str:
        """
        Create a fallback URL by keeping only the first 2 parts (up to 3rd dash)
        This won't work for all schools but helps in many cases
        
        Examples:
        - louisiana-state-university-and-agricultural-mechanical-college -> louisiana-state-university
        - university-of-pittsburgh-pittsburgh-campus -> university-of-pittsburgh
        
        Args:
            original_url: The original Niche URL that failed
            
        Returns:
            Simplified fallback URL or None if no simplification possible
        """
        # Extract the school name portion from URL
        # URL format: https://www.niche.com/colleges/{school-name}/
        if '/colleges/' not in original_url:
            return None
        
        # Get the school name part
        school_part = original_url.split('/colleges/')[1].rstrip('/')

        # Split by dashes
        parts = school_part.split('-')
        
        # Need at least 3 parts to simplify (keep first 2, remove rest)
        if len(parts) < 3:
            return None  # Can't simplify further
        
        # Take only the first 2 parts (everything before the 4rd dash)
        simplified_name = '-'.join(parts[:3])
        
        # Don't oversimplify - need meaningful content
        if not simplified_name or len(simplified_name) < 5:
            return None
        
        return f"{self.base_url}/{simplified_name}/"
    
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