"""
School Name to Baseball Rankings Name Matching System
Matches school names from school_data_general to team names in baseball_rankings_data
"""

from .school_name_matcher import SchoolNameMatcher
from .school_name_resolver import SchoolNameResolver, get_resolver

__all__ = ['SchoolNameMatcher', 'SchoolNameResolver', 'get_resolver']
