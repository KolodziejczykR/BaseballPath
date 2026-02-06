"""
Demographic preference filtering (size, admission rates, etc.)
"""

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))

from typing import List, Dict, Any, Union

from .base_filter import BaseFilter, FilterResult
from backend.utils.preferences_types import UserPreferences, VALID_GRADES


class DemographicFilter(BaseFilter):
    """Filter schools based on demographic preferences"""

    # School size mappings
    SIZE_RANGES = {
        "Small": (0, 2999),
        "Medium": (3000, 9999),
        "Large": (10000, 29999),
        "Very Large": (30000, float('inf'))
    }

    def __init__(self):
        super().__init__("Demographic Filter")

    def apply(self, schools: List[Dict[str, Any]], preferences: UserPreferences) -> FilterResult:
        """
        Filter schools based on demographic preferences

        Args:
            schools: List of school dictionaries
            preferences: User demographic preferences

        Returns:
            FilterResult with schools meeting demographic criteria
        """
        if not self._should_apply_filter(preferences):
            return self._create_result(
                schools, schools, False,
                "No demographic preferences specified"
            )

        filtered_schools = []

        for school in schools:
            if self._meets_demographic_criteria(school, preferences):
                filtered_schools.append(school)

        return self._create_result(schools, filtered_schools, True)

    def _should_apply_filter(self, preferences: UserPreferences) -> bool:
        """Check if demographic filtering should be applied"""
        return (
            preferences.preferred_school_size is not None or
            preferences.party_scene_preference is not None
        )

    def _meets_demographic_criteria(self, school: Dict[str, Any], preferences: UserPreferences) -> bool:
        """
        Check if a school meets the demographic criteria

        Args:
            school: School data dictionary
            preferences: User preferences

        Returns:
            True if school meets criteria, False otherwise
        """
        # Check school size preference
        if preferences.preferred_school_size:
            if not self._meets_size_preference(school, preferences.preferred_school_size):
                return False

        # Check party scene preference
        if preferences.party_scene_preference:
            if not self._meets_party_scene_preference(school, preferences.party_scene_preference):
                return False

        return True

    def _meets_size_preference(self, school: Dict[str, Any], preferred_sizes: List[str]) -> bool:
        """
        Check if school size matches preferences

        Args:
            school: School data
            preferred_sizes: List of preferred size categories

        Returns:
            True if school size matches any preferred size
        """
        enrollment = school.get('undergrad_enrollment')
        if enrollment is None:
            return True  # If size unknown, don't exclude

        for size_category in preferred_sizes:
            if size_category in self.SIZE_RANGES:
                min_size, max_size = self.SIZE_RANGES[size_category]
                if min_size <= enrollment <= max_size:
                    return True

        return False

    def _meets_party_scene_preference(self, school: Dict[str, Any], party_preference: List[str]) -> bool:
        """
        Check if school party scene matches preference

        Args:
            school: School data
            party_preference: List of preferences like ["Active", "Moderate"] or ["Quiet"]

        Returns:
            True if school matches any of the party scene preferences
        """
        party_grade = school.get('party_scene_grade', '')
        if not party_grade:
            return True  # If no grade, don't exclude

        # Define grade ranges for each preference
        grade_ranges = {
            "Active": ['A+', 'A'],
            "Moderate": ['A-', 'B+', 'B'],
            "Quiet": ['B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'F']
        }

        # Check if school's grade matches any of the preferred categories
        for preference in party_preference:
            if preference in grade_ranges and party_grade in grade_ranges[preference]:
                return True

        return False

    def _has_intended_major(self, school: Dict[str, Any], intended_major: str) -> bool:
        """
        Intended major matching is intentionally not implemented.
        This method is retained for potential future use.
        """
        return None
