"""
Tests for individual filter modules
"""

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

import pytest
from typing import List, Dict, Any

from backend.utils.preferences_types import UserPreferences
from backend.school_filtering.filters import (
    AcademicFilter,
    FinancialFilter,
    GeographicFilter,
    AthleticFilter,
    DemographicFilter
)


class TestAcademicFilter:
    """Test cases for AcademicFilter"""

    def setup_method(self):
        self.filter = AcademicFilter()
        self.test_schools = [
            {
                'school_name': 'Elite University',
                'academics_grade': 'A+',
                'admission_rate': 0.1,
                'avg_gpa': 3.9,
                'avg_sat': 1500
            },
            {
                'school_name': 'Good College',
                'academics_grade': 'B+',
                'admission_rate': 0.4,
                'avg_gpa': 3.5,
                'avg_sat': 1300
            },
            {
                'school_name': 'Average School',
                'academics_grade': 'C+',
                'admission_rate': 0.7,
                'avg_gpa': 3.0,
                'avg_sat': 1100
            }
        ]

    def test_no_academic_preferences(self):
        """Test filter when no academic preferences specified"""
        preferences = UserPreferences()
        result = self.filter.apply(self.test_schools, preferences)

        assert not result.filter_applied
        assert len(result.schools) == len(self.test_schools)

    def test_min_academic_rating_filter(self):
        """Test filtering by minimum academic rating"""
        preferences = UserPreferences(min_academic_rating='B+')
        result = self.filter.apply(self.test_schools, preferences)

        assert result.filter_applied
        assert len(result.schools) == 2  # Should exclude Average School
        school_names = [school['school_name'] for school in result.schools]
        assert 'Average School' not in school_names

    def test_admission_rate_filter(self):
        """Test filtering by admission rate floor"""
        preferences = UserPreferences(admit_rate_floor=30)  # 30%
        result = self.filter.apply(self.test_schools, preferences)

        assert result.filter_applied
        assert len(result.schools) == 2  # Should exclude Elite University (10% < 30%)

    def test_student_competitiveness(self):
        """Test student competitiveness checking"""
        # Student with low stats
        preferences = UserPreferences(gpa=2.5, sat=900)
        result = self.filter.apply(self.test_schools, preferences)

        # Should filter out schools where student isn't competitive
        filtered_names = [school['school_name'] for school in result.schools]
        assert 'Elite University' not in filtered_names


class TestFinancialFilter:
    """Test cases for FinancialFilter"""

    def setup_method(self):
        self.filter = FinancialFilter()
        self.test_schools = [
            {
                'school_name': 'Expensive Private',
                'state': 'CA',
                'in_state_tuition': 45000,
                'out_of_state_tuition': 50000,
                'avg_net_price': 35000
            },
            {
                'school_name': 'State University',
                'state': 'CA',
                'in_state_tuition': 15000,
                'out_of_state_tuition': 25000,
                'avg_net_price': 18000
            },
            {
                'school_name': 'Budget College',
                'state': 'TX',
                'in_state_tuition': 8000,
                'out_of_state_tuition': 18000,
                'avg_net_price': 12000
            }
        ]

    def test_no_financial_preferences(self):
        """Test filter when no financial preferences specified"""
        preferences = UserPreferences()
        result = self.filter.apply(self.test_schools, preferences)

        assert not result.filter_applied
        assert len(result.schools) == len(self.test_schools)

    def test_budget_filter_in_state(self):
        """Test budget filtering for in-state student"""
        preferences = UserPreferences(max_budget=20000, user_state='CA')
        result = self.filter.apply(self.test_schools, preferences)

        assert result.filter_applied
        # Should include State University (in-state: 15k) but exclude Expensive Private
        filtered_names = [school['school_name'] for school in result.schools]
        assert 'State University' in filtered_names
        assert 'Expensive Private' not in filtered_names

    def test_budget_filter_out_of_state(self):
        """Test budget filtering for out-of-state student"""
        preferences = UserPreferences(max_budget=20000, user_state='NY')
        result = self.filter.apply(self.test_schools, preferences)

        assert result.filter_applied
        # Should only include Budget College (out-of-state: 18k)
        filtered_names = [school['school_name'] for school in result.schools]
        assert 'Budget College' in filtered_names
        assert len(result.schools) == 1


class TestGeographicFilter:
    """Test cases for GeographicFilter"""

    def setup_method(self):
        self.filter = GeographicFilter()
        self.test_schools = [
            {'school_name': 'UCLA', 'state': 'CA'},
            {'school_name': 'NYU', 'state': 'NY'},
            {'school_name': 'UT Austin', 'state': 'TX'},
            {'school_name': 'University of Florida', 'state': 'FL'}
        ]

    def test_no_geographic_preferences(self):
        """Test filter when no geographic preferences specified"""
        preferences = UserPreferences()
        result = self.filter.apply(self.test_schools, preferences)

        assert not result.filter_applied
        assert len(result.schools) == len(self.test_schools)

    def test_preferred_states_filter(self):
        """Test filtering by preferred states"""
        preferences = UserPreferences(preferred_states=['CA', 'NY'])
        result = self.filter.apply(self.test_schools, preferences)

        assert result.filter_applied
        assert len(result.schools) == 2
        filtered_names = [school['school_name'] for school in result.schools]
        assert 'UCLA' in filtered_names
        assert 'NYU' in filtered_names

    def test_preferred_regions_filter(self):
        """Test filtering by preferred regions"""
        preferences = UserPreferences(preferred_regions=['West'])
        result = self.filter.apply(self.test_schools, preferences)

        assert result.filter_applied
        # Should include CA schools
        filtered_names = [school['school_name'] for school in result.schools]
        assert 'UCLA' in filtered_names


class TestAthleticFilter:
    """Test cases for AthleticFilter"""

    def setup_method(self):
        self.filter = AthleticFilter()
        self.test_schools = [
            {
                'school_name': 'Athletic Powerhouse',
                'athletics_grade': 'A+',
                'division': 'D1',
                'undergrad_enrollment': 30000
            },
            {
                'school_name': 'Decent Athletics',
                'athletics_grade': 'B',
                'division': 'D2',
                'undergrad_enrollment': 8000
            },
            {
                'school_name': 'Weak Athletics',
                'athletics_grade': 'D+',
                'division': 'D3',
                'undergrad_enrollment': 3000
            }
        ]

    def test_no_athletic_preferences(self):
        """Test filter when no athletic preferences specified"""
        preferences = UserPreferences()
        result = self.filter.apply(self.test_schools, preferences)

        assert not result.filter_applied
        assert len(result.schools) == len(self.test_schools)

    def test_min_athletics_rating_filter(self):
        """Test filtering by minimum athletics rating"""
        preferences = UserPreferences(min_athletics_rating='B')
        result = self.filter.apply(self.test_schools, preferences)

        assert result.filter_applied
        assert len(result.schools) == 2  # Should exclude Weak Athletics
        filtered_names = [school['school_name'] for school in result.schools]
        assert 'Weak Athletics' not in filtered_names

    def test_playing_time_priority_high(self):
        """Test filtering for high playing time priority"""
        preferences = UserPreferences(playing_time_priority='High')
        result = self.filter.apply(self.test_schools, preferences)

        assert result.filter_applied
        # Should prefer smaller schools or lower competition
        filtered_names = [school['school_name'] for school in result.schools]
        # Athletic Powerhouse (30k students, A+ athletics) should be filtered out
        assert 'Athletic Powerhouse' not in filtered_names


class TestDemographicFilter:
    """Test cases for DemographicFilter"""

    def setup_method(self):
        self.filter = DemographicFilter()
        self.test_schools = [
            {
                'school_name': 'Small Liberal Arts',
                'undergrad_enrollment': 2000,
                'party_scene_grade': 'C+',
                'school_type': 'Liberal Arts'
            },
            {
                'school_name': 'Medium University',
                'undergrad_enrollment': 8000,
                'party_scene_grade': 'B+',
                'school_type': 'University'
            },
            {
                'school_name': 'Large State School',
                'undergrad_enrollment': 25000,
                'party_scene_grade': 'A-',
                'school_type': 'University'
            }
        ]

    def test_no_demographic_preferences(self):
        """Test filter when no demographic preferences specified"""
        preferences = UserPreferences()
        result = self.filter.apply(self.test_schools, preferences)

        assert not result.filter_applied
        assert len(result.schools) == len(self.test_schools)

    def test_school_size_filter(self):
        """Test filtering by school size preference"""
        preferences = UserPreferences(preferred_school_size=['Small', 'Medium'])
        result = self.filter.apply(self.test_schools, preferences)

        assert result.filter_applied
        assert len(result.schools) == 2  # Should exclude Large State School
        filtered_names = [school['school_name'] for school in result.schools]
        assert 'Large State School' not in filtered_names

    def test_party_scene_filter(self):
        """Test filtering by party scene preference"""
        preferences = UserPreferences(party_scene_preference='Quiet')
        result = self.filter.apply(self.test_schools, preferences)

        assert result.filter_applied
        # Should only include schools with C+ or below party scene
        filtered_names = [school['school_name'] for school in result.schools]
        assert 'Small Liberal Arts' in filtered_names
        assert len(result.schools) == 1