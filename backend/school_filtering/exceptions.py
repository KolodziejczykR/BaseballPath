"""
Custom exceptions for the school filtering pipeline
"""

class FilteringError(Exception):
    """Base exception for filtering pipeline errors"""
    pass


class DatabaseConnectionError(FilteringError):
    """Exception raised when database connection fails"""
    pass


class InvalidPreferencesError(FilteringError):
    """Exception raised when user preferences are invalid or incomplete"""
    pass


class SchoolDataError(FilteringError):
    """Exception raised when school data is missing or invalid"""
    pass


class FilterExecutionError(FilteringError):
    """Exception raised when a filter fails to execute properly"""
    pass