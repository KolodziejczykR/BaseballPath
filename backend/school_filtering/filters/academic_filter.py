"""
Academic preference filtering
"""

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))

from typing import List, Dict, Any

from .base_filter import BaseFilter, FilterResult
from backend.utils.preferences_types import UserPreferences, VALID_GRADES


class AcademicFilter(BaseFilter):
    """Filter schools based on academic preferences"""

    def __init__(self):
        super().__init__("Academic Filter")

    def apply(self, schools: List[Dict[str, Any]], preferences: UserPreferences) -> FilterResult:
        """
        Filter schools based on academic preferences

        Args:
            schools: List of school dictionaries
            preferences: User academic preferences

        Returns:
            FilterResult with schools meeting academic criteria
        """
        if not self._should_apply_filter(preferences):
            return self._create_result(
                schools, schools, False,
                "No academic preferences specified"
            )

        filtered_schools = []

        for school in schools:
            if self._meets_academic_criteria(school, preferences):
                filtered_schools.append(school)

        return self._create_result(schools, filtered_schools, True)

    def _should_apply_filter(self, preferences: UserPreferences) -> bool:
        """Check if academic filtering should be applied"""
        return (
            preferences.min_academic_rating is not None or
            preferences.min_student_satisfaction_rating is not None or
            preferences.admit_rate_floor is not None or
            preferences.sat is not None or
            preferences.act is not None
        )

    def _meets_academic_criteria(self, school: Dict[str, Any], preferences: UserPreferences) -> bool:
        """
        Check if a school meets the academic criteria

        Args:
            school: School data dictionary
            preferences: User preferences

        Returns:
            True if school meets criteria, False otherwise
        """
        # Check minimum academic rating
        if preferences.min_academic_rating:
            school_rating = school.get('academics_grade')
            if not school_rating or not self._meets_grade_requirement(
                school_rating, preferences.min_academic_rating
            ):
                return False

        # Check admission rate floor
        if preferences.admit_rate_floor is not None:
            admission_rate = school.get('admission_rate')
            if admission_rate is None or admission_rate < (preferences.admit_rate_floor / 100.0):
                return False

        # Check if student's stats are competitive (if provided)
        if not self._is_student_competitive(school, preferences):
            return False

        # Check minimum student satisfaction rating
        if preferences.min_student_satisfaction_rating:
            school_satisfaction_rating = school.get('student_life_grade')
            if not school_satisfaction_rating or not self._meets_grade_requirement(
                school_satisfaction_rating, preferences.min_student_satisfaction_rating
            ):
                return False

        return True

    def _meets_grade_requirement(self, school_grade: str, min_grade: str) -> bool:
        """
        Check if school grade meets minimum requirement

        Args:
            school_grade: School's academic grade (e.g., 'A-', 'B+')
            min_grade: Minimum required grade

        Returns:
            True if school grade meets or exceeds minimum
        """
        if school_grade not in VALID_GRADES or min_grade not in VALID_GRADES:
            return False

        school_index = VALID_GRADES.index(school_grade)
        min_index = VALID_GRADES.index(min_grade)

        # Lower index = better grade (A+ is index 0, F is index 12)
        return school_index <= min_index

    def _is_student_competitive(self, school: Dict[str, Any], preferences: UserPreferences) -> bool:
        """
        Check if student's academic stats are competitive for the school

        Args:
            school: School data
            preferences: User preferences with academic stats

        Returns:
            True if student is competitive or no stats provided
        """
        # If no student stats provided, assume competitive
        if not any([preferences.sat, preferences.act]):
            return True

        # Check SAT competitiveness
        if preferences.sat and school.get('avg_sat'):
            # Allow flexibility - within +- 100 points of school sat is True
            if abs(preferences.sat - school.get('avg_sat', 0)) > 100:
                return False

        # Check ACT competitiveness
        if preferences.act and school.get('avg_act'):
            # Allow flexibility - within +- 2 points of school act is True
            if abs(preferences.act - school.get('avg_act', 0)) > 2:
                return False

        return True

    def _meets_academic_environment(self, school: Dict[str, Any], env_preference: str) -> bool:
        """
        Check if school matches academic environment preference

        Args:
            school: School data
            env_preference: "High-academic", "Balanced", or "Flexible"

        Returns:
            True if school matches environment preference
        """
        school_rating = school.get('academics_grade', '')

        if env_preference == "High-academic":
            # Require A- or better
            return self._meets_grade_requirement(school_rating, "A-")
        elif env_preference == "Balanced":
            # Accept B+ or better
            return self._meets_grade_requirement(school_rating, "B")
        elif env_preference == "Flexible":
            # Accept C+ or better
            return self._meets_grade_requirement(school_rating, "C+")

        return True