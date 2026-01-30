"""
Athletic preference filtering
"""

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))

from typing import List, Dict, Any, Optional, Union

from .base_filter import BaseFilter, FilterResult
from backend.utils.preferences_types import UserPreferences, VALID_GRADES


class AthleticFilter(BaseFilter):
    """Filter schools based on athletic preferences"""

    def __init__(self):
        super().__init__("Athletic Filter")

    def apply(self, schools: List[Dict[str, Any]], preferences: UserPreferences) -> FilterResult:
        """
        Filter schools based on athletic preferences

        Args:
            schools: List of school dictionaries
            preferences: User athletic preferences

        Returns:
            FilterResult with schools meeting athletic criteria
        """
        if not self._should_apply_filter(preferences):
            return self._create_result(
                schools, schools, False,
                "No athletic preferences specified"
            )

        filtered_schools = []

        for school in schools:
            if self._meets_athletic_criteria(school, preferences):
                filtered_schools.append(school)

        return self._create_result(schools, filtered_schools, True)

    def _should_apply_filter(self, preferences: UserPreferences) -> bool:
        """Check if athletic filtering should be applied"""
        return preferences.min_athletics_rating is not None

    def _meets_athletic_criteria(self, school: Dict[str, Any], preferences: UserPreferences) -> bool:
        """
        Check if a school meets the athletic criteria

        Args:
            school: School data dictionary
            preferences: User preferences

        Returns:
            True if school meets criteria, False otherwise
        """
        # Check minimum athletics rating
        if preferences.min_athletics_rating:
            school_rating = school.get('total_athletics_grade')
            if not school_rating or not self._meets_grade_requirement(
                school_rating, preferences.min_athletics_rating
            ):
                return False

        return True

    def _meets_grade_requirement(self, school_grade: str, min_grade: str) -> bool:
        """
        Check if school grade meets minimum requirement

        Args:
            school_grade: School's athletics grade
            min_grade: Minimum required grade

        Returns:
            True if school grade meets or exceeds minimum
        """
        if school_grade not in VALID_GRADES or min_grade not in VALID_GRADES:
            return False

        school_index = VALID_GRADES.index(school_grade)
        min_index = VALID_GRADES.index(min_grade)

        # Lower index = better grade
        return school_index <= min_index

    def _meets_playing_time_criteria(self, school: Dict[str, Any], priorities: List[str]) -> bool:
        """
        Check if school matches playing time priority

        Args:
            school: School data
            priorities: List of priorities like ["High", "Medium"] or ["Low"]

        Returns:
            True if school matches any of the playing time expectations
        """

        # TODO: Implement playing time matching logic, this won't work
        # - Complex calculation requiring:
        #   * Current roster depth by position
        #   * Graduating seniors by position
        #   * Team's recruiting class by position
        #   * Competition level/difficulty

        # Get athletics level and competitiveness indicators
        athletics_grade = school.get('total_athletics_grade', '')
        division = school.get('division', '').upper()
        enrollment = school.get('undergrad_enrollment', 0)

        # Check if school meets any of the priority criteria
        for priority in priorities:
            if priority == "High":
                # Want significant playing time - prefer smaller schools or lower athletics grades
                if (enrollment < 10000 or  # Smaller schools
                    athletics_grade in ['C+', 'C', 'C-', 'D+', 'D', 'D-', 'F'] or  # Lower competition
                    division in ['D2', 'D3', 'NAIA']):  # Lower divisions
                    return True
            elif priority == "Medium":
                # Balanced approach - medium competition is fine
                if (enrollment < 25000 or  # Not the largest schools
                    athletics_grade not in ['A+', 'A']):  # Not the most competitive
                    return True
            elif priority == "Low":
                # Don't mind limited playing time - any school is fine
                return True

        return False
