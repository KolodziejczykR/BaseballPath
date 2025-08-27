"""
College Scoreboard API Retrieval for BaseballPATH
Retrieves school statistics from the U.S. Department of Education's College Scorecard API
"""

import os
import sys
import time
import requests
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv
from difflib import SequenceMatcher

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.utils.scraping_types import SchoolStatisticsAPI

load_dotenv()

class CollegeScorecardRetriever:
    """Retriever for college statistics using the College Scorecard API"""
    
    def __init__(self, api_key: str = None, delay: float = 1.0):
        """
        Initialize with College Scorecard API key
        
        Args:
            api_key: College Scorecard API key (get from https://api.data.gov/signup/)
            delay: Delay between requests in seconds
        """
        self.api_key = api_key or os.getenv("COLLEGE_SCORECARD_API_KEY")
        if not self.api_key:
            raise ValueError("College Scorecard API key is required. Set COLLEGE_SCORECARD_API_KEY environment variable or pass as parameter.")
        
        self.delay = delay
        self.base_url = "https://api.data.gov/ed/collegescorecard/v1/schools"
        self.session = requests.Session()
        
        # Setup session headers
        self.session.headers.update({
            'User-Agent': 'Baseball-Recruitment-Platform/1.0',
            'Accept': 'application/json'
        })
    
    def get_school_statistics(self, school_names: List[str], cities: List[str] = None) -> List[SchoolStatisticsAPI]:
        """
        Retrieve statistics for multiple schools from College Scorecard API
        
        Args:
            school_names: List of school names to retrieve statistics for
            cities: Optional list of cities (format: "City, State" or "City") to help with matching
            
        Returns:
            List of SchoolStatisticsAPI objects with school statistics
        """
        results = []
        
        # If cities provided, make sure lists are same length
        if cities and len(cities) != len(school_names):
            raise ValueError("If cities are provided, the list must be the same length as school_names")
        
        for i, school_name in enumerate(school_names):
            city = cities[i] if cities else None
            location_info = f" in {city}" if city else ""
            print(f"Retrieving stats for {school_name}{location_info} ({i+1}/{len(school_names)})")
            
            stats = self._get_single_school_stats(school_name, city)
            if stats:
                results.append(stats)
            else:
                # Create placeholder with None/default values if school not found
                results.append(SchoolStatisticsAPI(
                    school_city=city or "Unknown",
                    undergrad_enrollment=0,
                    in_state_tuition=0,
                    out_of_state_tuition=0,
                    admission_rate=0.0,
                    avg_sat=0,
                    avg_act=0
                ))
            
            # Rate limiting
            if i < len(school_names) - 1:
                time.sleep(self.delay)
        
        return results
    
    def _get_single_school_stats(self, school_name: str, city: str = None) -> Optional[SchoolStatisticsAPI]:
        """
        Retrieve statistics for a single school
        
        Args:
            school_name: Name of the school to look up
            city: Optional city/state to help narrow the search (format: "City, State" or "City")
            
        Returns:
            SchoolStatisticsAPI object or None if not found
        """
        # If city provided, try city-based fuzzy search first
        if city:
            result = self._search_by_city_with_fuzzy_match(school_name, city)
            if result:
                return result
        
        # Fallback to original name-based search
        return self._search_by_name_only(school_name)
    
    def _search_by_city_with_fuzzy_match(self, school_name: str, city: str) -> Optional[SchoolStatisticsAPI]:
        """
        Search all schools in a city, then use fuzzy matching to find the best match
        
        Args:
            school_name: Name of school to match
            city: City/state to search in
            
        Returns:
            SchoolStatisticsAPI object or None if not found
        """
        try:
            # Parse city/state
            city_part, state_part = self._parse_city_state(city)
            
            # Search all schools in this city/state
            search_params = {
                'api_key': self.api_key,
                'fields': (
                    'id,'
                    'school.name,'
                    'school.city,'
                    'school.state,'
                    'latest.student.size,'
                    'latest.cost.tuition.in_state,'
                    'latest.cost.tuition.out_of_state,'
                    'latest.admissions.admission_rate.overall,'
                    'latest.admissions.sat_scores.average.overall,'
                    'latest.admissions.act_scores.midpoint.cumulative'
                ),
                'per_page': 50  # Get more results for city-based search
            }
            
            # Add location filters
            if city_part:
                search_params['school.city'] = city_part
            if state_part:
                search_params['school.state'] = state_part
            
            response = self.session.get(self.base_url, params=search_params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            schools = data.get('results', [])
            
            if not schools:
                print(f"  No schools found in {city}")
                return None
            
            print(f"  Found {len(schools)} schools in {city}, finding best match...")
            
            # Find best fuzzy match
            best_match = self._find_best_fuzzy_match(school_name, schools)
            if best_match:
                return self._extract_statistics(best_match)
            
            return None
            
        except Exception as e:
            print(f"  Error in city-based search: {e}")
            return None
    
    def _search_by_name_only(self, school_name: str) -> Optional[SchoolStatisticsAPI]:
        """
        Original name-based search as fallback
        
        Args:
            school_name: Name of school to search for
            
        Returns:
            SchoolStatisticsAPI object or None if not found
        """
        try:
            search_params = {
                'api_key': self.api_key,
                'school.name': school_name,
                'fields': (
                    'id,'
                    'school.name,'
                    'school.city,'
                    'school.state,'
                    'latest.student.size,'
                    'latest.cost.tuition.in_state,'
                    'latest.cost.tuition.out_of_state,'
                    'latest.admissions.admission_rate.overall,'
                    'latest.admissions.sat_scores.average.overall,'
                    'latest.admissions.act_scores.midpoint.cumulative'
                ),
                'per_page': 20
            }
            
            response = self.session.get(self.base_url, params=search_params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            schools = data.get('results', [])
            
            if not schools:
                print(f"  No schools found for '{school_name}'")
                return None
            
            # Use fuzzy matching logic (same as city-based search)
            best_match = self._find_best_fuzzy_match(school_name, schools)
            if best_match:
                return self._extract_statistics(best_match)
            
            return None
            
        except Exception as e:
            print(f"  Error in name-based search: {e}")
            return None
    
    def _parse_city_state(self, city: str) -> tuple[str, str]:
        """
        Parse city/state string into components
        
        Args:
            city: City string in format "City, State" or "City"
            
        Returns:
            Tuple of (city_part, state_part)
        """
        if ',' in city:
            city_part, state_part = [x.strip() for x in city.split(',', 1)]
            if len(state_part) == 2:
                state_part = state_part.upper()
            return city_part, state_part
        else:
            return city, None
    
    def _find_best_fuzzy_match(self, search_name: str, schools: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Find best match - exact first, then fuzzy matching
        
        Args:
            search_name: Name to search for
            schools: List of school data from API
            
        Returns:
            Best matching school data or None
        """
        search_name_lower = search_name.lower()
        
        # First, check for exact matches
        for school in schools:
            school_name = school.get('school.name', '').lower()
            if school_name == search_name_lower:
                print(f"  Exact match found: '{search_name}' with '{school.get('school.name', 'Unknown')}'")
                return school
        
        # If no exact match, use fuzzy matching
        best_score = 0
        best_match = None
        
        for school in schools:
            school_name = school.get('school.name', '').lower()
            
            # Check minimum enrollment threshold (500+ students)
            enrollment = school.get('latest.student.size', 0) or 0
            if enrollment < 500:
                continue
            
            # Multiple similarity checks
            score = max(
                self._fuzzy_similarity(search_name_lower, school_name),
                self._word_similarity(search_name_lower, school_name),
                self._acronym_similarity(search_name_lower, school_name)
            )
            
            if score > best_score and score > 0.4:  # Lower threshold for fuzzy matching
                best_score = score
                best_match = school
        
        if best_match:
            print(f"  Fuzzy matched '{search_name}' with '{best_match.get('school.name', 'Unknown')}' (score: {best_score:.2f})")
        
        return best_match
    
    def _fuzzy_similarity(self, name1: str, name2: str) -> float:
        """
        Calculate fuzzy similarity using SequenceMatcher
        
        Args:
            name1: First name
            name2: Second name
            
        Returns:
            Similarity score between 0 and 1
        """
        return SequenceMatcher(None, name1, name2).ratio()
    
    def _acronym_similarity(self, search_name: str, school_name: str) -> float:
        """
        Check if search name could be an acronym of school name
        
        Args:
            search_name: Search term (e.g., "georgia tech")
            school_name: Full school name (e.g., "georgia institute of technology")
            
        Returns:
            Similarity score between 0 and 1
        """
        # Check if search contains key words from full name
        search_words = set(search_name.split())
        school_words = set(school_name.split())
        
        # Remove common words
        common_words = {'university', 'college', 'of', 'the', 'at', 'in', 'and', 'state', 'institute', 'technology'}
        search_words = search_words - common_words
        school_words = school_words - common_words
        
        if not search_words:
            return 0.0
        
        # Check for partial matches (e.g., "tech" in "technology")
        matches = 0
        for search_word in search_words:
            for school_word in school_words:
                if search_word in school_word or school_word in search_word:
                    if len(search_word) >= 3:  # Avoid matching very short words
                        matches += 1
                        break
        
        return matches / len(search_words)
    
    def _find_best_match(self, search_name: str, schools: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Find the best matching school from search results
        
        Args:
            search_name: The original search name
            schools: List of school data from API
            
        Returns:
            Best matching school data or None
        """
        search_name_lower = search_name.lower()
        
        # First, try exact name match
        for school in schools:
            school_name = school.get('school.name', '').lower()
            if school_name == search_name_lower:
                return school
        
        # Then try partial matches
        best_score = 0
        best_match = None
        
        for school in schools:
            school_name = school.get('school.name', '').lower()
            
            # Calculate simple similarity score
            score = self._calculate_similarity(search_name_lower, school_name)
            if score > best_score and score > 0.6:  # Minimum similarity threshold
                best_score = score
                best_match = school
        
        if best_match:
            print(f"  Matched '{search_name}' with '{best_match.get('school.name', 'Unknown')}'")
        
        return best_match
    
    def _word_similarity(self, name1: str, name2: str) -> float:
        """
        Calculate similarity between two school names
        
        Args:
            name1: First school name
            name2: Second school name
            
        Returns:
            Similarity score between 0 and 1
        """
        # Simple word-based similarity
        words1 = set(name1.split())
        words2 = set(name2.split())
        
        # Remove common words that don't help with matching
        common_words = {'university', 'college', 'of', 'the', 'at', 'in', 'and', 'state', 'tech', 'institute'}
        words1 = words1 - common_words
        words2 = words2 - common_words
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _extract_statistics(self, school_data: Dict[str, Any]) -> SchoolStatisticsAPI:
        """
        Extract statistics from school data and create SchoolStatisticsAPI object
        
        Args:
            school_data: Raw school data from API
            
        Returns:
            SchoolStatisticsAPI object with extracted statistics
        """
        def safe_int(value, default=0):
            """Safely convert value to int"""
            if value is None:
                return default
            try:
                return int(value)
            except (ValueError, TypeError):
                return default
        
        def safe_float(value, default=0.0):
            """Safely convert value to float"""
            if value is None:
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default
        
        # Extract city (with state if available)
        city = school_data.get('school.city', 'Unknown')
        state = school_data.get('school.state', '')
        if state and city != 'Unknown':
            city = f"{city}, {state}"
        
        return SchoolStatisticsAPI(
            school_city=city,
            undergrad_enrollment=safe_int(school_data.get('latest.student.size')),
            in_state_tuition=safe_int(school_data.get('latest.cost.tuition.in_state')),
            out_of_state_tuition=safe_int(school_data.get('latest.cost.tuition.out_of_state')),
            admission_rate=safe_float(school_data.get('latest.admissions.admission_rate.overall')),
            avg_sat=safe_int(school_data.get('latest.admissions.sat_scores.average.overall')),
            avg_act=safe_int(school_data.get('latest.admissions.act_scores.midpoint.cumulative'))
        )


def main():
    """Test the College Scorecard retriever with complex cases"""
    test_schools = [
        # Exact matches
        "University of Georgia",
        "Union College",
        
        # Complex fuzzy matches
        "Georgia Tech",                    # Should match "Georgia Institute of Technology-Main Campus"
        "Cal Tech",                       # Should match "California Institute of Technology"
        "Massachusetts Institute of Technology",
        
        "Penn State",                     # Should match "Pennsylvania State University-Main Campus"
        "UC Berkeley",                    # Should match "University of California-Berkeley"
        "New York University",           # Should match "New York University"
        "Virginia Tech",                  # Should match "Virginia Polytechnic Institute and State University"
        "Carnegie Mellon",               # Should match "Carnegie Mellon University"
        "Northwestern",                   # Should match "Northwestern University"
        
        # Tricky cases with common words
        "Saint Joseph's University",     # vs other Saint Joseph schools
        "University of Miami",           # vs Miami University (Ohio)
        "George Washington University",   # vs other George Washington schools

        "University of Michigan",         # vs other Michigan universities
    ]
    
    test_cities = [
        # Exact matches
        "Athens, GA",
        "Schenectady, NY",
        
        # Complex fuzzy matches
        "Atlanta, GA",      # Georgia Tech
        "Pasadena, CA",     # Cal Tech
        "Cambridge, MA",    # MIT
        "University Park, PA", # Penn State
        "Berkeley, CA",     # UC Berkeley
        "New York, NY",     # New York University
        "Blacksburg, VA",   # Virginia Tech
        "Pittsburgh, PA",   # Carnegie Mellon
        "Evanston, IL",     # Northwestern
        
        # Tricky cases
        "Philadelphia, PA",  # Saint Joseph's
        "Coral Gables, FL",  # University of Miami (not Miami University in Ohio)
        "Washington, DC",   # George Washington University

        "Ann Arbor, MI",    # University of Michigan
    ]
    
    try:
        retriever = CollegeScorecardRetriever(delay=3.0)
        
        print("Testing with complex cases and city information:")
        print("=" * 60)
        results = retriever.get_school_statistics(test_schools, test_cities)
        
        # Print results with categories
        print("\n" + "=" * 60)
        print("RESULTS SUMMARY:")
        print("=" * 60)
        
        successful_matches = 0
        for i, stats in enumerate(results):
            school_name = test_schools[i]
            
            # Check if this looks like a successful match (enrollment > 500 so valid school)
            if stats.undergrad_enrollment > 500:
                successful_matches += 1
                status = "✅ SUCCESS"
            else:
                status = "❌ FAILED"
            
            print(f"\n{status} {school_name}:")
            print(f"  City: {stats.school_city}")
            print(f"  Undergrad Enrollment: {stats.undergrad_enrollment:,}")
            print(f"  In-State Tuition: ${stats.in_state_tuition:,}")
            print(f"  Out-of-State Tuition: ${stats.out_of_state_tuition:,}")
            print(f"  Admission Rate: {stats.admission_rate:.1%}")
            print(f"  Average SAT: {stats.avg_sat}")
            print(f"  Average ACT: {stats.avg_act}")
        
        print(f"\n" + "=" * 60)
        print(f"SUMMARY: {successful_matches}/{len(test_schools)} successful matches ({successful_matches/len(test_schools)*100:.1f}%)")
        print("=" * 60)
            
    except ValueError as e:
        print(f"\n❌ ERROR: {e}")
        print("Please set your COLLEGE_SCORECARD_API_KEY environment variable.")
        print("Get your free API key at: https://api.data.gov/signup/")
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")


if __name__ == "__main__":
    main()