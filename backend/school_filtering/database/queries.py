"""
Database query operations for school filtering
"""

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))

from typing import List, Dict, Any, Optional
from supabase import Client

from .connection import SupabaseConnection
from ..exceptions import SchoolDataError


class SchoolDataQueries:
    """Database query operations for school data"""

    def __init__(self):
        self.connection = SupabaseConnection()

    @property
    def client(self) -> Client:
        """Get Supabase client"""
        return self.connection.client

    def get_all_schools(self) -> List[Dict[str, Any]]:
        """
        Retrieve all schools from the school_data_general table

        Returns:
            List of school dictionaries with all available data
        """
        try:
            response = self.client.table('school_data_general').select('*').execute()

            if not response.data:
                return []

            return response.data

        except Exception as e:
            raise SchoolDataError(f"Failed to retrieve schools: {str(e)}")

    def get_schools_by_division_group(self, division_group: str) -> List[Dict[str, Any]]:
        """
        Retrieve schools filtered by division_group

        Args:
            division_group: The division group to filter by (e.g., "Power 4 D1", "Non-P4 D1", "Non-D1")

        Returns:
            List of school dictionaries matching the division group
        """
        try:
            response = self.client.table('school_data_general')\
                .select('*')\
                .eq('division_group', division_group)\
                .execute()

            return response.data or []

        except Exception as e:
            raise SchoolDataError(f"Failed to retrieve schools by division group: {str(e)}")

    def get_schools_by_division_groups(self, division_groups: List[str], limit_per_group: Optional[Dict[str, int]] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Retrieve schools from multiple division groups with optional limits per group

        Args:
            division_groups: List of division groups to retrieve
            limit_per_group: Optional dictionary mapping division_group -> max_schools

        Returns:
            Dictionary mapping division_group -> list of schools
        """
        try:
            results = {}

            for division_group in division_groups:
                query = self.client.table('school_data_general')\
                    .select('*')\
                    .eq('division_group', division_group)

                # Apply limit if specified
                if limit_per_group and division_group in limit_per_group:
                    query = query.limit(limit_per_group[division_group])

                response = query.execute()
                results[division_group] = response.data or []

            return results

        except Exception as e:
            raise SchoolDataError(f"Failed to retrieve schools by division groups: {str(e)}")

    def get_schools_by_names(self, school_names: List[str]) -> List[Dict[str, Any]]:
        """
        Retrieve specific schools by their names

        Args:
            school_names: List of school names to retrieve

        Returns:
            List of school dictionaries
        """
        if not school_names:
            return []

        try:
            response = self.client.table('school_data_general')\
                .select('*')\
                .in_('school_name', school_names)\
                .execute()

            return response.data or []

        except Exception as e:
            raise SchoolDataError(f"Failed to retrieve schools by names: {str(e)}")

    def get_schools_with_filters(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Retrieve schools with database-level filtering for performance

        Args:
            filters: Dictionary of column:value pairs for filtering

        Returns:
            List of filtered school dictionaries
        """
        try:
            query = self.client.table('school_data_general').select('*')

            # Apply filters dynamically
            for column, value in filters.items():
                if isinstance(value, list):
                    query = query.in_(column, value)
                elif isinstance(value, tuple) and len(value) == 2:
                    # Range filter (min, max)
                    min_val, max_val = value
                    if min_val is not None:
                        query = query.gte(column, min_val)
                    if max_val is not None:
                        query = query.lte(column, max_val)
                else:
                    query = query.eq(column, value)

            response = query.execute()
            return response.data or []

        except Exception as e:
            raise SchoolDataError(f"Failed to retrieve filtered schools: {str(e)}")

    def get_available_columns(self) -> List[str]:
        """
        Get list of available columns in school_data_general table

        Returns:
            List of column names
        """
        try:
            # Get one record to inspect columns
            response = self.client.table('school_data_general').select('*').limit(1).execute()

            if response.data and len(response.data) > 0:
                return list(response.data[0].keys())
            else:
                # If no data, we'll need to introspect the table schema differently
                # This is a fallback approach
                return []

        except Exception as e:
            raise SchoolDataError(f"Failed to get table columns: {str(e)}")

    def get_school_count(self) -> int:
        """
        Get total number of schools in the database

        Returns:
            Total count of schools
        """
        try:
            response = self.client.table('school_data_general')\
                .select('*', count='exact')\
                .limit(1)\
                .execute()

            return response.count or 0

        except Exception as e:
            raise SchoolDataError(f"Failed to get school count: {str(e)}")