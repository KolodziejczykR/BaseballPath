"""
Financial preference filtering
"""

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))

from typing import List, Dict, Any

from .base_filter import BaseFilter, FilterResult
from backend.utils.preferences_types import UserPreferences


class FinancialFilter(BaseFilter):
    """Filter schools based on financial preferences"""

    def __init__(self):
        super().__init__("Financial Filter")

    def apply(self, schools: List[Dict[str, Any]], preferences: UserPreferences) -> FilterResult:
        """
        Filter schools based on financial preferences

        Args:
            schools: List of school dictionaries
            preferences: User financial preferences

        Returns:
            FilterResult with schools meeting financial criteria
        """
        if not self._should_apply_filter(preferences):
            return self._create_result(
                schools, schools, False,
                "No financial preferences specified"
            )

        filtered_schools = []

        for school in schools:
            if self._meets_financial_criteria(school, preferences):
                filtered_schools.append(school)

        return self._create_result(schools, filtered_schools, True)

    def _should_apply_filter(self, preferences: UserPreferences) -> bool:
        """Check if financial filtering should be applied"""
        return preferences.max_budget is not None

    def _meets_financial_criteria(self, school: Dict[str, Any], preferences: UserPreferences) -> bool:
        """
        Check if a school meets the financial criteria

        Args:
            school: School data dictionary
            preferences: User preferences

        Returns:
            True if school meets criteria, False otherwise
        """
        # Check maximum budget
        if preferences.max_budget is not None:
            if not self._meets_budget_requirement(school, preferences):
                return False

        return True

    def _meets_budget_requirement(self, school: Dict[str, Any], preferences: UserPreferences) -> bool:
        """
        Check if school meets budget requirement

        Args:
            school: School data
            preferences: User preferences with budget

        Returns:
            True if school is within budget
        """
        # Determine which tuition to use based on user's state
        tuition = self.get_tuition(school, preferences)

        return tuition <= preferences.max_budget

    def get_tuition(self, school: Dict[str, Any], preferences: UserPreferences):
        # Determine which tuition to use based on user's state
        if preferences.user_state:
            school_state = school.get('school_state', '').upper()
            user_state = preferences.user_state.upper()

            if school_state == user_state:
                # In-state tuition
                tuition = school.get('in_state_tuition')
            else:
                # Out-of-state tuition
                tuition = school.get('out_of_state_tuition')
        else:
            # If no user state specified, use out-of-state tuition (more conservative)
            tuition = school.get('out_of_state_tuition')

        return tuition
    