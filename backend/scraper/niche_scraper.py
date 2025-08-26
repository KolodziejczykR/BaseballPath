"""
Niche.com Rating Scraper for BaseballPATH
Specialized scraper for college ratings and data from Niche.com
"""

import os
import sys
import time
import re
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict
from selenium.webdriver.common.by import By
from dotenv import load_dotenv

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.scraper.selenium_driver import SeleniumDriverManager, normalize_text, is_valid_grade

load_dotenv()

@dataclass
class NicheRatings:
    """Data class for Niche.com college ratings and information"""
    school_name: str
    overall_grade: str = None
    academics_grade: str = None
    campus_life_grade: str = None
    athletics_grade: str = None
    value_grade: str = None
    student_life_grade: str = None
    party_scene_grade: str = None
    diversity_grade: str = None
    location_grade: str = None
    safety_grade: str = None
    enrollment: str = None
    acceptance_rate: str = None
    tuition: str = None
    sat_range: str = None
    act_range: str = None
    student_faculty_ratio: str = None
    niche_url: str = None
    error: str = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)

class NicheScraper:
    """Specialized scraper for Niche.com college data"""
    
    def __init__(self, driver_manager: SeleniumDriverManager):
        """
        Initialize with existing WebDriver manager
        
        Args:
            driver_manager: Configured SeleniumDriverManager instance
        """
        self.driver_manager = driver_manager
        self.base_url = "https://www.niche.com/colleges"
    
    def scrape_school_ratings(self, school_name: str, custom_url: str = None) -> NicheRatings:
        """
        Scrape comprehensive Niche.com ratings for a school
        
        Args:
            school_name: Official school name
            custom_url: Optional custom Niche URL if known
            
        Returns:
            NicheRatings object with all available data
        """
        print(f"Scraping Niche ratings for: {school_name}")
        
        try:
            # Build Niche URL
            niche_url = custom_url or self._build_niche_url(school_name)
            print(f"Niche URL: {niche_url}")
            
            # Load page
            if not self.driver_manager.get(niche_url):
                return NicheRatings(school_name=school_name, 
                                  error="Failed to load Niche page")
            
            # Initialize ratings object
            ratings = NicheRatings(school_name=school_name, niche_url=niche_url)
            
            # Check if page loaded correctly
            if not self._verify_niche_page():
                return NicheRatings(school_name=school_name, niche_url=niche_url,
                                  error="Invalid Niche page or school not found")
            
            # Scrape all rating categories
            ratings.overall_grade = self._extract_overall_grade()
            self._extract_category_grades(ratings)
            self._extract_school_stats(ratings)
            
            return ratings
            
        except Exception as e:
            print(f"Error scraping Niche data for {school_name}: {e}")
            return NicheRatings(school_name=school_name, error=str(e))
    
    def _build_niche_url(self, school_name: str) -> str:
        """Build Niche URL from school name"""
        # Convert school name to Niche URL format
        # Examples: "University of Georgia" -> "university-of-georgia"
        #          "Georgia Tech" -> "georgia-institute-of-technology"
        
        url_name = school_name.lower()
        
        # Common replacements for Niche URLs
        replacements = {
            'university of ': '',
            'college of ': '',
            ' university': '',
            ' college': '',
            ' institute of technology': '-institute-of-technology',
            ' tech': '-institute-of-technology',
            'st. ': 'saint-',
            ' & ': '-',
            ' and ': '-',
            ' ': '-'
        }
        
        for old, new in replacements.items():
            url_name = url_name.replace(old, new)
        
        # Clean up multiple dashes and special characters
        url_name = re.sub(r'[^a-z0-9-]', '', url_name)
        url_name = re.sub(r'-+', '-', url_name).strip('-')
        
        return f"{self.base_url}/{url_name}/"
    
    def _verify_niche_page(self) -> bool:
        """Verify that we're on a valid Niche college page"""
        keywords = ['college', 'university', 'niche', 'ratings', 'grades']
        return self.driver_manager.page_contains_keywords(keywords)
    
    def _extract_overall_grade(self) -> Optional[str]:
        """Extract the main overall grade"""
        selectors = [
            "[data-testid='report-card-grade']",
            ".report-card__grade",
            ".overall-grade",
            ".grade--large",
            "h2.grade"
        ]
        
        for selector in selectors:
            element, found = self.driver_manager.find_element_safe(selector)
            if found:
                grade_text = self.driver_manager.extract_text_safe(element)
                if is_valid_grade(grade_text):
                    return grade_text
        
        return None
    
    def _extract_category_grades(self, ratings: NicheRatings):
        """Extract all category grades (academics, athletics, etc.)"""
        
        # Grade category mappings
        grade_categories = {
            'academics_grade': [
                "[data-testid='academics-grade']",
                ".academics .grade",
                "[aria-label*='academics' i] .grade"
            ],
            'athletics_grade': [
                "[data-testid='athletics-grade']", 
                ".athletics .grade",
                "[aria-label*='athletics' i] .grade",
                "[aria-label*='sports' i] .grade"
            ],
            'campus_life_grade': [
                "[data-testid='campus-life-grade']",
                ".campus-life .grade",
                "[aria-label*='campus life' i] .grade"
            ],
            'value_grade': [
                "[data-testid='value-grade']",
                ".value .grade",
                "[aria-label*='value' i] .grade"
            ],
            'student_life_grade': [
                "[data-testid='student-life-grade']",
                ".student-life .grade"
            ],
            'party_scene_grade': [
                "[data-testid='party-scene-grade']",
                ".party-scene .grade"
            ],
            'diversity_grade': [
                "[data-testid='diversity-grade']",
                ".diversity .grade"
            ],
            'location_grade': [
                "[data-testid='location-grade']",
                ".location .grade"
            ],
            'safety_grade': [
                "[data-testid='safety-grade']",
                ".safety .grade"
            ]
        }
        
        for rating_field, selectors in grade_categories.items():
            for selector in selectors:
                element, found = self.driver_manager.find_element_safe(selector)
                if found:
                    grade_text = self.driver_manager.extract_text_safe(element)
                    if is_valid_grade(grade_text):
                        setattr(ratings, rating_field, grade_text)
                        break
    
    def _extract_school_stats(self, ratings: NicheRatings):
        """Extract school statistics (enrollment, acceptance rate, etc.)"""
        
        # Stat extraction mappings
        stat_selectors = {
            'enrollment': [
                "[data-testid='enrollment']",
                ".enrollment .value",
                "[aria-label*='enrollment' i]"
            ],
            'acceptance_rate': [
                "[data-testid='acceptance-rate']", 
                ".acceptance-rate .value",
                "[aria-label*='acceptance rate' i]"
            ],
            'tuition': [
                "[data-testid='tuition']",
                ".tuition .value", 
                "[aria-label*='tuition' i]"
            ],
            'sat_range': [
                "[data-testid='sat-range']",
                ".sat-range .value",
                "[aria-label*='sat' i]"
            ],
            'act_range': [
                "[data-testid='act-range']",
                ".act-range .value",
                "[aria-label*='act' i]"
            ],
            'student_faculty_ratio': [
                "[data-testid='student-faculty-ratio']",
                ".student-faculty-ratio .value"
            ]
        }
        
        for stat_field, selectors in stat_selectors.items():
            for selector in selectors:
                element, found = self.driver_manager.find_element_safe(selector, timeout=3)
                if found:
                    stat_text = self.driver_manager.extract_text_safe(element)
                    if stat_text:
                        setattr(ratings, stat_field, normalize_text(stat_text))
                        break
    
    def scrape_multiple_schools(self, school_names: List[str]) -> Dict[str, NicheRatings]:
        """
        Scrape ratings for multiple schools
        
        Args:
            school_names: List of school names to scrape
            
        Returns:
            Dictionary mapping school names to NicheRatings objects
        """
        results = {}
        
        for i, school_name in enumerate(school_names):
            print(f"\n--- Niche scraping {i+1}/{len(school_names)}: {school_name} ---")
            
            ratings = self.scrape_school_ratings(school_name)
            results[school_name] = ratings
            
            # Rate limiting between requests
            if i < len(school_names) - 1:
                time.sleep(self.driver_manager.delay)
        
        return results

def main():
    """Test the Niche scraper"""
    test_schools = [
        "University of Georgia",
        "Georgia Tech", 
        "Emory University",
        "Kennesaw State University"
    ]
    
    with SeleniumDriverManager(headless=True, delay=2.0) as driver_manager:
        scraper = NicheScraper(driver_manager)
        
        results = scraper.scrape_multiple_schools(test_schools)
        
        # Print results
        for school_name, ratings in results.items():
            print(f"\n{school_name}:")
            print(f"  Overall: {ratings.overall_grade}")
            print(f"  Academics: {ratings.academics_grade}")
            print(f"  Athletics: {ratings.athletics_grade}")
            print(f"  Enrollment: {ratings.enrollment}")
            print(f"  Error: {ratings.error}")

if __name__ == "__main__":
    main()