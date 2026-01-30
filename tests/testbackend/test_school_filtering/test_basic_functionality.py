"""
Basic functionality tests for school filtering system
Tests the core components that are already implemented
"""

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

import pytest
from typing import Dict, List, Any

from backend.utils.preferences_types import UserPreferences
from backend.utils.school_match_types import (
    PreferenceCategory, NiceToHaveType, NiceToHaveMatch, NiceToHaveMiss,
    SchoolMatch, FilteringResult, NICE_TO_HAVE_MAPPING
)


class TestBasicFunctionality:
    """Test basic functionality that should work"""

    def test_user_preferences_creation(self):
        """Test creating user preferences"""
        preferences = UserPreferences(
            user_state='CA',
            max_budget=30000,
            min_academic_rating='B+',
            preferred_states=['CA', 'TX']
        )

        assert preferences.user_state == 'CA'
        assert preferences.max_budget == 30000
        assert preferences.min_academic_rating == 'B+'
        assert preferences.preferred_states == ['CA', 'TX']

    def test_must_have_preferences(self):
        """Test must-have preference functionality"""
        preferences = UserPreferences(
            user_state='CA',
            max_budget=30000,
            min_academic_rating='B+'
        )

        # Initially no must-haves
        must_haves = preferences.get_must_haves()
        assert len(must_haves) == 0

        # Make budget must-have
        preferences.make_must_have('max_budget')
        must_haves = preferences.get_must_haves()
        assert 'max_budget' in must_haves

        # Check nice-to-haves
        nice_to_haves = preferences.get_nice_to_haves()
        assert 'min_academic_rating' in nice_to_haves
        assert 'max_budget' not in nice_to_haves

    def test_school_match_creation(self):
        """Test creating school matches"""
        school_data = {
            'school_name': 'Test University',
            'school_state': 'CA',
            'academics_grade': 'B+',
            'overall_athletics_grade': 'A-'
        }

        school_match = SchoolMatch(
            school_name='Test University',
            school_data=school_data,
            division_group='Non-P4 D1'
        )

        assert school_match.school_name == 'Test University'
        assert school_match.division_group == 'Non-P4 D1'
        assert school_match.school_data == school_data

    def test_nice_to_have_match(self):
        """Test nice-to-have match creation"""
        match = NiceToHaveMatch(
            preference_type=NiceToHaveType.GEOGRAPHIC,
            preference_name='preferred_states',
            user_value=['CA', 'TX'],
            school_value='CA',
            description='School is located in California, matching your preferred states.'
        )

        assert match.preference_type == NiceToHaveType.GEOGRAPHIC
        assert match.preference_name == 'preferred_states'
        assert 'California' in match.description

    def test_nice_to_have_miss(self):
        """Test nice-to-have miss creation"""
        miss = NiceToHaveMiss(
            preference_type=NiceToHaveType.ACADEMIC_FIT,
            preference_name='min_academic_rating',
            user_value='A-',
            school_value='B+',
            reason='School academic rating (B+) is below your minimum requirement (A-).'
        )

        assert miss.preference_type == NiceToHaveType.ACADEMIC_FIT
        assert miss.preference_name == 'min_academic_rating'
        assert 'below' in miss.reason

    def test_filtering_result(self):
        """Test filtering result structure"""
        school_match = SchoolMatch(
            school_name='Test School',
            school_data={'school_name': 'Test School'},
            division_group='Non-D1'
        )

        result = FilteringResult(
            must_have_count=5,
            school_matches=[school_match],
            total_possible_schools=100,
            filtering_summary={'filtered': 95}
        )

        assert result.must_have_count == 5
        assert len(result.school_matches) == 1
        assert result.total_possible_schools == 100

    def test_preference_mapping(self):
        """Test nice-to-have preference mapping"""
        assert 'preferred_states' in NICE_TO_HAVE_MAPPING
        assert 'sat' in NICE_TO_HAVE_MAPPING
        assert 'min_academic_rating' in NICE_TO_HAVE_MAPPING

        assert NICE_TO_HAVE_MAPPING['preferred_states'] == NiceToHaveType.GEOGRAPHIC
        assert NICE_TO_HAVE_MAPPING['sat'] == NiceToHaveType.ACADEMIC_FIT

    def test_school_match_summary(self):
        """Test school match summary generation"""
        school_match = SchoolMatch(
            school_name='Test University',
            school_data={'school_name': 'Test University'},
            division_group='Non-P4 D1'
        )

        # Add a match
        match = NiceToHaveMatch(
            preference_type=NiceToHaveType.GEOGRAPHIC,
            preference_name='preferred_states',
            user_value=['CA'],
            school_value='CA',
            description='School is in California.'
        )
        school_match.add_nice_to_have_match(match)

        # Add a miss
        miss = NiceToHaveMiss(
            preference_type=NiceToHaveType.ACADEMIC_FIT,
            preference_name='sat',
            user_value=1400,
            school_value=1200,
            reason='Your SAT is higher than school average.'
        )
        school_match.add_nice_to_have_miss(miss)

        summary = school_match.get_match_summary()

        assert summary['school_name'] == 'Test University'
        assert summary['total_nice_to_have_matches'] == 1
        assert len(summary['pros']) == 1
        assert len(summary['cons']) == 1

    def test_preference_categories(self):
        """Test preference category enums"""
        assert PreferenceCategory.MUST_HAVE.value == "must_have"
        assert PreferenceCategory.NICE_TO_HAVE.value == "nice_to_have"

    def test_nice_to_have_types(self):
        """Test nice-to-have type enums"""
        assert NiceToHaveType.GEOGRAPHIC.value == "geographic"
        assert NiceToHaveType.ACADEMIC_FIT.value == "academic_fit"
        assert NiceToHaveType.SCHOOL_CHARACTERISTICS.value == "school_characteristics"
        assert NiceToHaveType.ATHLETIC_PREFERENCES.value == "athletic_preferences"
        assert NiceToHaveType.DEMOGRAPHIC.value == "demographic"

    def test_user_preferences_validation(self):
        """Test user preferences basic validation"""
        # Valid preferences should work
        preferences = UserPreferences(
            user_state='CA',
            sat=1350,
            act=30
        )

        assert preferences.sat == 1350
        assert preferences.act == 30

    def test_multiselect_preferences(self):
        """Test multi-select preference handling"""
        preferences = UserPreferences(
            user_state='CA',
            preferred_states=['CA', 'TX', 'FL'],
            preferred_regions=['West', 'South'],
            preferred_school_size=['Medium', 'Large']
        )

        assert isinstance(preferences.preferred_states, list)
        assert len(preferences.preferred_states) == 3
        assert 'CA' in preferences.preferred_states
        assert 'TX' in preferences.preferred_states

        assert isinstance(preferences.preferred_regions, list)
        assert 'West' in preferences.preferred_regions

    def test_dynamic_must_have_conversion(self):
        """Test converting nice-to-have to must-have"""
        preferences = UserPreferences(
            user_state='CA',
            max_budget=30000,
            min_academic_rating='B+',
            preferred_states=['CA']
        )

        # Initially all are nice-to-have
        nice_to_haves = preferences.get_nice_to_haves()
        assert 'max_budget' in nice_to_haves
        assert 'min_academic_rating' in nice_to_haves
        assert 'preferred_states' in nice_to_haves

        # Convert budget to must-have
        preferences.make_must_have('max_budget')

        must_haves = preferences.get_must_haves()
        nice_to_haves = preferences.get_nice_to_haves()

        assert 'max_budget' in must_haves
        assert 'max_budget' not in nice_to_haves
        assert 'min_academic_rating' in nice_to_haves
        assert 'preferred_states' in nice_to_haves

    def test_grade_values_exist(self):
        """Test that grade validation is working"""
        from backend.utils.preferences_types import VALID_GRADES

        assert 'A+' in VALID_GRADES
        assert 'A' in VALID_GRADES
        assert 'A-' in VALID_GRADES
        assert 'B+' in VALID_GRADES
        assert 'F' in VALID_GRADES

        # Test grade order (lower index = better grade)
        a_plus_index = VALID_GRADES.index('A+')
        f_index = VALID_GRADES.index('F')
        assert a_plus_index < f_index  # A+ (0) should be before F (12)