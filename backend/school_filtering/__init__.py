"""
School Filtering Pipeline

Industry-standard modular filtering system for school recommendations
based on user preferences and ML predictions.
"""

from .pipeline import SchoolFilteringPipeline
from .exceptions import FilteringError, DatabaseConnectionError, InvalidPreferencesError

__all__ = [
    'SchoolFilteringPipeline',
    'FilteringError',
    'DatabaseConnectionError',
    'InvalidPreferencesError'
]