"""
Async database query operations for school filtering with connection pooling and retry logic
"""

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))

import asyncio
import logging
from typing import List, Dict, Any, Optional
from supabase import Client

from .async_connection import AsyncSupabaseConnection
from ..exceptions import SchoolDataError

logger = logging.getLogger(__name__)


class AsyncSchoolDataQueries:
    """Async database query operations for school data with resilience patterns"""

    def __init__(self, connection: Optional[AsyncSupabaseConnection] = None):
        self.connection = connection or AsyncSupabaseConnection()

    async def get_all_schools(self) -> List[Dict[str, Any]]:
        """
        Retrieve all schools from the school_data_general table

        Returns:
            List of school dictionaries with all available data
        """
        async def _get_all_schools_query(client: Client) -> List[Dict[str, Any]]:
            logger.debug("Executing get_all_schools query")
            response = client.table('school_data_general').select('*').execute()

            if not response.data:
                logger.warning("No schools found in database")
                return []

            logger.info(f"Retrieved {len(response.data)} schools from database")
            return response.data

        try:
            return await self.connection.execute_with_retry(_get_all_schools_query)
        except Exception as e:
            raise SchoolDataError(f"Failed to retrieve schools: {str(e)}")

    async def get_schools_by_division_group(self, division_group: str) -> List[Dict[str, Any]]:
        """
        Retrieve schools filtered by division_group

        Args:
            division_group: The division group to filter by (e.g., "Power 4 D1", "Non-P4 D1", "Non-D1")

        Returns:
            List of school dictionaries matching the division group
        """
        async def _get_schools_by_division_query(client: Client, div_group: str) -> List[Dict[str, Any]]:
            logger.debug(f"Executing get_schools_by_division_group query for: {div_group}")
            response = client.table('school_data_general')\
                .select('*')\
                .eq('division_group', div_group)\
                .execute()

            result = response.data or []
            logger.info(f"Retrieved {len(result)} schools for division group: {div_group}")
            return result

        try:
            return await self.connection.execute_with_retry(_get_schools_by_division_query, division_group)
        except Exception as e:
            raise SchoolDataError(f"Failed to retrieve schools by division group: {str(e)}")

    async def get_schools_by_division_groups(self,
                                           division_groups: List[str],
                                           limit_per_group: Optional[Dict[str, int]] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Retrieve schools from multiple division groups with optional limits per group

        Args:
            division_groups: List of division groups to retrieve
            limit_per_group: Optional dictionary mapping division_group -> max_schools

        Returns:
            Dictionary mapping division_group -> list of schools
        """
        async def _get_schools_by_division_groups_query(client: Client,
                                                       div_groups: List[str],
                                                       limits: Optional[Dict[str, int]]) -> Dict[str, List[Dict[str, Any]]]:
            logger.debug(f"Executing get_schools_by_division_groups query for: {div_groups}")
            results = {}

            # Execute queries for each division group
            for division_group in div_groups:
                query = client.table('school_data_general')\
                    .select('*')\
                    .eq('division_group', division_group)

                # Apply limit if specified
                if limits and division_group in limits:
                    query = query.limit(limits[division_group])

                response = query.execute()
                schools = response.data or []
                results[division_group] = schools
                logger.debug(f"Retrieved {len(schools)} schools for division group: {division_group}")

            total_schools = sum(len(schools) for schools in results.values())
            logger.info(f"Retrieved {total_schools} total schools across {len(div_groups)} division groups")
            return results

        try:
            return await self.connection.execute_with_retry(_get_schools_by_division_groups_query, division_groups, limit_per_group)
        except Exception as e:
            raise SchoolDataError(f"Failed to retrieve schools by division groups: {str(e)}")

    async def get_schools_by_names(self, school_names: List[str]) -> List[Dict[str, Any]]:
        """
        Retrieve specific schools by their names

        Args:
            school_names: List of school names to retrieve

        Returns:
            List of school dictionaries
        """
        if not school_names:
            logger.debug("No school names provided, returning empty list")
            return []

        async def _get_schools_by_names_query(client: Client, names: List[str]) -> List[Dict[str, Any]]:
            logger.debug(f"Executing get_schools_by_names query for {len(names)} schools")
            response = client.table('school_data_general')\
                .select('*')\
                .in_('school_name', names)\
                .execute()

            result = response.data or []
            logger.info(f"Retrieved {len(result)} schools by names")
            return result

        try:
            return await self.connection.execute_with_retry(_get_schools_by_names_query, school_names)
        except Exception as e:
            raise SchoolDataError(f"Failed to retrieve schools by names: {str(e)}")

    async def get_schools_with_filters(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Retrieve schools with database-level filtering for performance

        Args:
            filters: Dictionary of column:value pairs for filtering

        Returns:
            List of filtered school dictionaries
        """
        async def _get_schools_with_filters_query(client: Client, filter_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
            logger.debug(f"Executing get_schools_with_filters query with {len(filter_dict)} filters")
            query = client.table('school_data_general').select('*')

            # Apply filters dynamically
            for column, value in filter_dict.items():
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
            result = response.data or []
            logger.info(f"Retrieved {len(result)} schools with filters")
            return result

        try:
            return await self.connection.execute_with_retry(_get_schools_with_filters_query, filters)
        except Exception as e:
            raise SchoolDataError(f"Failed to retrieve filtered schools: {str(e)}")

    async def get_available_columns(self) -> List[str]:
        """
        Get list of available columns in school_data_general table

        Returns:
            List of column names
        """
        async def _get_available_columns_query(client: Client) -> List[str]:
            logger.debug("Executing get_available_columns query")
            # Get one record to inspect columns
            response = client.table('school_data_general').select('*').limit(1).execute()

            if response.data and len(response.data) > 0:
                columns = list(response.data[0].keys())
                logger.info(f"Retrieved {len(columns)} column names")
                return columns
            else:
                logger.warning("No data found to determine columns")
                return []

        try:
            return await self.connection.execute_with_retry(_get_available_columns_query)
        except Exception as e:
            raise SchoolDataError(f"Failed to get table columns: {str(e)}")

    async def get_school_count(self) -> int:
        """
        Get total number of schools in the database

        Returns:
            Total count of schools
        """
        async def _get_school_count_query(client: Client) -> int:
            logger.debug("Executing get_school_count query")
            response = client.table('school_data_general')\
                .select('*', count='exact')\
                .limit(1)\
                .execute()

            count = response.count or 0
            logger.info(f"Total school count: {count}")
            return count

        try:
            return await self.connection.execute_with_retry(_get_school_count_query)
        except Exception as e:
            raise SchoolDataError(f"Failed to get school count: {str(e)}")

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the database connection

        Returns:
            Dictionary with health status and connection stats
        """
        try:
            start_time = asyncio.get_event_loop().time()

            # Test basic connectivity
            connection_ok = await self.connection.test_connection()

            # Get connection stats
            stats = await self.connection.get_connection_stats()

            # Test a simple query
            count = await self.get_school_count()

            end_time = asyncio.get_event_loop().time()

            return {
                'status': 'healthy' if connection_ok else 'unhealthy',
                'connection_test': connection_ok,
                'school_count': count,
                'response_time_ms': round((end_time - start_time) * 1000, 2),
                'connection_stats': stats,
                'timestamp': asyncio.get_event_loop().time()
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': asyncio.get_event_loop().time()
            }

    async def close(self):
        """Clean up database connections"""
        if self.connection:
            await self.connection.close()


# Global instance for dependency injection
async_school_queries = AsyncSchoolDataQueries()