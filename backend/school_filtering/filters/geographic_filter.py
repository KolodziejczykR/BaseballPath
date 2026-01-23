"""
Geographic preference filtering
"""

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))

from typing import List, Dict, Any

from .base_filter import BaseFilter, FilterResult
from backend.utils.preferences_types import UserPreferences


class GeographicFilter(BaseFilter):
    """Filter schools based on geographic preferences"""

    # Regional mappings
    REGION_STATES = {
        "Northeast": ["CT", "ME", "MA", "NH", "RI", "VT", "NJ", "NY", "PA"],
        "Mid-Atlantic": ["DE", "DC", "MD", "NJ", "NY", "PA", "VA", "WV"],
        "Midwest": ["IL", "IN", "IA", "KS", "MI", "MN", "MO", "NE", "ND", "OH", "SD", "WI"],
        "South": ["AL", "AR", "DE", "DC", "FL", "GA", "KY", "LA", "MD", "MS", "NC", "OK", "SC", "TN", "TX", "VA", "WV"],
        "West": ["AK", "AZ", "CA", "CO", "HI", "ID", "MT", "NV", "NM", "OR", "UT", "WA", "WY"]
    }

    def __init__(self):
        super().__init__("Geographic Filter")

    def apply(self, schools: List[Dict[str, Any]], preferences: UserPreferences) -> FilterResult:
        """
        Filter schools based on geographic preferences

        Args:
            schools: List of school dictionaries
            preferences: User geographic preferences

        Returns:
            FilterResult with schools meeting geographic criteria
        """
        if not self._should_apply_filter(preferences):
            return self._create_result(
                schools, schools, False,
                "No geographic preferences specified"
            )

        filtered_schools = []

        for school in schools:
            if self._meets_geographic_criteria(school, preferences):
                filtered_schools.append(school)

        return self._create_result(schools, filtered_schools, True)

    def _should_apply_filter(self, preferences: UserPreferences) -> bool:
        """Check if geographic filtering should be applied"""
        return (
            preferences.preferred_states is not None or
            preferences.preferred_regions is not None
        )

    def _meets_geographic_criteria(self, school: Dict[str, Any], preferences: UserPreferences) -> bool:
        """
        Check if a school meets the geographic criteria

        Args:
            school: School data dictionary
            preferences: User preferences

        Returns:
            True if school meets criteria, False otherwise
        """
        school_state = school.get('school_state', '').upper()

        # Check preferred states
        if preferences.preferred_states:
            preferred_states_upper = [state.upper() for state in preferences.preferred_states]
            if school_state in preferred_states_upper:
                return True

        # Check preferred regions
        if preferences.preferred_regions:
            for region in preferences.preferred_regions:
                if region in self.REGION_STATES:
                    region_states = [state.upper() for state in self.REGION_STATES[region]]
                    if school_state in region_states:
                        return True

        # If both states and regions are specified but school doesn't match either, exclude
        if preferences.preferred_states or preferences.preferred_regions:
            return False

        return True