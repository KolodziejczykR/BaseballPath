"""
School Filtering Pipeline

Industry-standard modular filtering system for school recommendations
based on user preferences and ML predictions.
"""

from .exceptions import FilteringError, DatabaseConnectionError, InvalidPreferencesError

__all__ = [
    'FilteringError',
    'DatabaseConnectionError',
    'InvalidPreferencesError'
]