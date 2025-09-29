"""
Filter modules for school preference filtering
"""

from .base_filter import BaseFilter, FilterResult
from .academic_filter import AcademicFilter
from .financial_filter import FinancialFilter
from .geographic_filter import GeographicFilter
from .athletic_filter import AthleticFilter
from .demographic_filter import DemographicFilter

__all__ = [
    'BaseFilter',
    'FilterResult',
    'AcademicFilter',
    'FinancialFilter',
    'GeographicFilter',
    'AthleticFilter',
    'DemographicFilter'
]