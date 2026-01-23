"""
Abstract base class for all preference filters
"""

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from dataclasses import dataclass

from backend.utils.preferences_types import UserPreferences


@dataclass
class FilterResult:
    """Result of applying a filter"""
    schools: List[Dict[str, Any]]
    filter_name: str
    schools_filtered_out: int
    filter_applied: bool
    reason: str = ""


class BaseFilter(ABC):
    """Abstract base class for all preference filters"""

    def __init__(self, filter_name: str):
        self.filter_name = filter_name

    @abstractmethod
    def apply(self, schools: List[Dict[str, Any]], preferences: UserPreferences) -> FilterResult:
        """
        Apply the filter to a list of schools based on user preferences

        Args:
            schools: List of school dictionaries to filter
            preferences: User preferences to filter by

        Returns:
            FilterResult containing filtered schools and metadata
        """
        pass

    def _should_apply_filter(self, preferences: UserPreferences) -> bool:
        """
        Determine if this filter should be applied based on preferences
        Override in subclasses to define specific conditions

        Args:
            preferences: User preferences to check

        Returns:
            True if filter should be applied, False otherwise
        """
        return True

    def _create_result(self,
                      original_schools: List[Dict[str, Any]],
                      filtered_schools: List[Dict[str, Any]],
                      applied: bool,
                      reason: str = "") -> FilterResult:
        """
        Create a FilterResult object

        Args:
            original_schools: Schools before filtering
            filtered_schools: Schools after filtering
            applied: Whether the filter was actually applied
            reason: Reason for not applying filter (if applicable)

        Returns:
            FilterResult object
        """
        return FilterResult(
            schools=filtered_schools,
            filter_name=self.filter_name,
            schools_filtered_out=len(original_schools) - len(filtered_schools),
            filter_applied=applied,
            reason=reason
        )