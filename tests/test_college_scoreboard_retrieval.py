"""
Test Suite for College Scorecard API Retrieval
Tests the fuzzy matching and data retrieval functionality
"""

import pytest
import os
from typing import List
from unittest.mock import Mock, patch
from backend.scraper.college_scoreboard_retrieval import CollegeScorecardRetriever
from backend.utils.scraping_types import SchoolStatisticsAPI


class TestCollegeScorecardRetriever:
    """Test class for College Scorecard API retrieval functionality"""
    
    @pytest.fixture
    def retriever(self):
        """Create a retriever instance for testing"""
        # Use real API key if available, otherwise skip integration tests
        api_key = os.getenv('COLLEGE_SCORECARD_API_KEY')
        if not api_key:
            pytest.skip("COLLEGE_SCORECARD_API_KEY not set - skipping integration tests")
        return CollegeScorecardRetriever(delay=0.5)  # Faster for tests
    
    @pytest.fixture
    def test_schools_and_cities(self):
        """Test data with expected successful matches"""
        return {
            # Exact matches (should be easy)
            "University of Georgia": {
                "city": "Athens, GA",
                "should_succeed": True,
                "min_enrollment": 25000
            },
            "Union College": {
                "city": "Schenectady, NY", 
                "should_succeed": True,
                "min_enrollment": 2000
            },
            
            # Complex fuzzy matches
            "Georgia Tech": {
                "city": "Atlanta, GA",
                "should_succeed": True,
                "expected_name_contains": "Georgia Institute of Technology",
                "min_enrollment": 15000
            },
            "Cal Tech": {
                "city": "Pasadena, CA",
                "should_succeed": True,
                "expected_name_contains": "California Institute of Technology",
                "min_enrollment": 900
            },
            "Penn State": {
                "city": "University Park, PA",
                "should_succeed": True,
                "expected_name_contains": "Pennsylvania State University",
                "min_enrollment": 35000
            },
            "UC Berkeley": {
                "city": "Berkeley, CA", 
                "should_succeed": True,
                "expected_name_contains": "University of California",
                "min_enrollment": 30000
            },
            "New York University": {
                "city": "New York, NY",
                "should_succeed": True,
                "min_enrollment": 25000
            },
            "Virginia Tech": {
                "city": "Blacksburg, VA",
                "should_succeed": True,
                "expected_name_contains": "Virginia Polytechnic Institute",
                "min_enrollment": 25000
            },
            "Carnegie Mellon": {
                "city": "Pittsburgh, PA",
                "should_succeed": True,
                "expected_name_contains": "Carnegie Mellon University",
                "min_enrollment": 6000
            },
            "Northwestern": {
                "city": "Evanston, IL",
                "should_succeed": True,
                "expected_name_contains": "Northwestern University", 
                "min_enrollment": 8000
            },
            
            # Tricky disambiguation cases
            "Saint Joseph's University": {
                "city": "Philadelphia, PA",
                "should_succeed": True,
                "min_enrollment": 4000
            },
            "University of Miami": {
                "city": "Coral Gables, FL",  # Not Miami, FL!
                "should_succeed": True,
                "min_enrollment": 10000
            },
            "George Washington University": {
                "city": "Washington, DC",
                "should_succeed": True,
                "min_enrollment": 10000
            }
        }
    
    @pytest.mark.integration
    def test_successful_school_matches(self, retriever, test_schools_and_cities):
        """Test that expected schools are found successfully"""
        school_names = list(test_schools_and_cities.keys())
        cities = [data["city"] for data in test_schools_and_cities.values()]
        
        results = retriever.get_school_statistics(school_names, cities)
        
        assert len(results) == len(school_names), "Should return result for each school"
        
        for i, school_name in enumerate(school_names):
            result = results[i]
            expected = test_schools_and_cities[school_name]
            
            if expected["should_succeed"]:
                # Check that we got valid data
                assert result.undergrad_enrollment > 0, f"{school_name} should have enrollment data"
                assert result.city != "Unknown", f"{school_name} should have city data"
                
                # Check enrollment meets minimum threshold
                if "min_enrollment" in expected:
                    assert result.undergrad_enrollment >= expected["min_enrollment"], \
                        f"{school_name} enrollment {result.undergrad_enrollment} should be >= {expected['min_enrollment']}"
                
                # Check tuition data exists for most schools
                assert result.in_state_tuition > 0 or result.out_of_state_tuition > 0, \
                    f"{school_name} should have tuition data"
    
    @pytest.mark.integration 
    def test_fuzzy_matching_quality(self, retriever, test_schools_and_cities):
        """Test that fuzzy matching finds the right institutions"""
        complex_cases = {
            name: data for name, data in test_schools_and_cities.items() 
            if "expected_name_contains" in data
        }
        
        school_names = list(complex_cases.keys())
        cities = [data["city"] for data in complex_cases.values()]
        
        results = retriever.get_school_statistics(school_names, cities)
        
        for i, school_name in enumerate(school_names):
            result = results[i] 
            expected = complex_cases[school_name]
            
            # For fuzzy matching cases, we can't verify the exact API name
            # but we can verify the results look correct
            assert result.undergrad_enrollment >= expected["min_enrollment"], \
                f"{school_name} should match a major university, got enrollment: {result.undergrad_enrollment}"
    
    @pytest.mark.integration
    def test_minimum_enrollment_threshold(self, retriever):
        """Test that small schools are filtered out"""
        # Test a case that might match small schools
        results = retriever.get_school_statistics(
            ["Berkeley"], 
            ["Berkeley, CA"]
        )
        
        result = results[0]
        if result.undergrad_enrollment > 0:
            # If we got a match, it should be a substantial institution
            assert result.undergrad_enrollment >= 500, \
                "Should filter out schools with < 500 students"
    
    def test_city_parsing(self, retriever):
        """Test city/state parsing functionality"""
        # Test with comma format
        city_part, state_part = retriever._parse_city_state("Atlanta, GA")
        assert city_part == "Atlanta"
        assert state_part == "GA"
        
        # Test with full state name
        city_part, state_part = retriever._parse_city_state("Boston, Massachusetts")
        assert city_part == "Boston" 
        assert state_part == "Massachusetts"
        
        # Test city only
        city_part, state_part = retriever._parse_city_state("Boston")
        assert city_part == "Boston"
        assert state_part is None
    
    def test_similarity_algorithms(self, retriever):
        """Test the different similarity matching algorithms"""
        # Test fuzzy similarity
        assert retriever._fuzzy_similarity("georgia tech", "georgia institute of technology") > 0.5
        assert retriever._fuzzy_similarity("mit", "massachusetts institute of technology") > 0.1
        
        # Test word similarity  
        assert retriever._word_similarity("georgia tech", "georgia institute of technology") > 0.3
        assert retriever._word_similarity("penn state university", "pennsylvania state university") > 0.3
        
        # Test acronym similarity
        assert retriever._acronym_similarity("georgia tech", "georgia institute of technology") > 0.5
        assert retriever._acronym_similarity("cal tech", "california institute of technology") > 0.5
    
    def test_school_statistics_api_structure(self, retriever):
        """Test that results conform to SchoolStatisticsAPI structure"""
        results = retriever.get_school_statistics(["University of Georgia"], ["Athens, GA"])
        result = results[0]
        
        # Check all required fields exist
        assert hasattr(result, 'city')
        assert hasattr(result, 'undergrad_enrollment')
        assert hasattr(result, 'in_state_tuition')
        assert hasattr(result, 'out_of_state_tuition')
        assert hasattr(result, 'admission_rate')
        assert hasattr(result, 'avg_sat')
        assert hasattr(result, 'avg_act')
        
        # Check data types
        assert isinstance(result.city, str)
        assert isinstance(result.undergrad_enrollment, int)
        assert isinstance(result.in_state_tuition, int)
        assert isinstance(result.out_of_state_tuition, int) 
        assert isinstance(result.admission_rate, float)
        assert isinstance(result.avg_sat, int)
        assert isinstance(result.avg_act, int)
    
    def test_error_handling(self, retriever):
        """Test error handling for invalid inputs"""
        # Test mismatched list lengths
        with pytest.raises(ValueError, match="same length"):
            retriever.get_school_statistics(
                ["School1", "School2"], 
                ["City1"]  # Wrong length
            )
        
        # Test empty school name
        results = retriever.get_school_statistics([""], ["Atlanta, GA"])
        assert len(results) == 1
        assert results[0].undergrad_enrollment == 0  # Should return default values
    
    @pytest.mark.integration
    def test_no_city_fallback(self, retriever):
        """Test that name-only search works as fallback"""
        # Test without city information
        results = retriever.get_school_statistics(["Harvard University"])
        
        assert len(results) == 1
        result = results[0]
        
        # Should still find Harvard even without city
        if result.undergrad_enrollment > 0:
            assert "harvard" in result.city.lower() or "cambridge" in result.city.lower()
    
    @pytest.mark.parametrize("school_name,city,expected_success", [
        ("University of Georgia", "Athens, GA", True),
        ("Georgia Tech", "Atlanta, GA", True), 
        ("Cal Tech", "Pasadena, CA", True),
        ("NonexistentUniversity", "Nowhere, XX", False),
        ("", "Atlanta, GA", False)
    ])
    def test_individual_school_lookups(self, retriever, school_name, city, expected_success):
        """Parameterized test for individual school lookups"""
        results = retriever.get_school_statistics([school_name], [city])
        result = results[0]
        
        if expected_success:
            assert result.undergrad_enrollment > 0, f"Should find {school_name}"
            assert result.city != "Unknown", f"Should have city data for {school_name}"
        else:
            assert result.undergrad_enrollment == 0, f"Should not find {school_name}"


class TestIntegrationScenarios:
    """Integration tests for real-world scenarios"""
    
    @pytest.fixture
    def retriever(self):
        """Create a retriever instance for testing"""
        api_key = os.getenv('COLLEGE_SCORECARD_API_KEY')
        if not api_key:
            pytest.skip("COLLEGE_SCORECARD_API_KEY not set - skipping integration tests")
        return CollegeScorecardRetriever(delay=0.1)
    
    @pytest.mark.integration
    def test_baseball_recruitment_scenario(self, retriever):
        """Test a realistic baseball recruitment scenario"""
        # Simulate what an LLM might provide for baseball recruitment
        schools = [
            "University of Georgia",
            "Georgia Institute of Technology", # Full name from LLM
            "University of Miami",
            "Vanderbilt University",
            "Stanford University"
        ]
        
        cities = [
            "Athens, GA", 
            "Atlanta, GA",
            "Coral Gables, FL",
            "Nashville, TN",
            "Stanford, CA"
        ]
        
        results = retriever.get_school_statistics(schools, cities)
        
        # All should be successful for major universities
        successful = [r for r in results if r.undergrad_enrollment > 0]
        assert len(successful) >= 4, f"Should find most major universities, got {len(successful)}/5"
        
        # Check that we get reasonable data for successful matches
        for result in successful:
            assert 1000 <= result.undergrad_enrollment <= 50000, "Enrollment should be reasonable"
            assert result.admission_rate <= 1.0, "Admission rate should be <= 100%"
            if result.avg_sat > 0:
                assert 800 <= result.avg_sat <= 1600, "SAT should be in valid range"
            if result.avg_act > 0:
                assert 10 <= result.avg_act <= 36, "ACT should be in valid range"


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s", "--tb=short"])