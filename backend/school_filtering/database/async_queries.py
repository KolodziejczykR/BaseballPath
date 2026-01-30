"""
Async database query operations for school filtering with connection pooling and retry logic

Database Schema:
- school_data_general: Main school data (school_name, school_state, tuition, etc.)
- school_baseball_ranking_name_mapping: Maps school_name → team_name
- baseball_rankings_data: Has division_group and baseball rankings by team_name
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
from backend.utils.school_group_constants import NON_D1

logger = logging.getLogger(__name__)


class AsyncSchoolDataQueries:
    """Async database query operations for school data with resilience patterns

    Division group is stored in baseball_rankings_data, accessed via:
    school_data_general.school_name → school_baseball_ranking_name_mapping.team_name → baseball_rankings_data.division_group
    """

    def __init__(self, connection: Optional[AsyncSupabaseConnection] = None):
        self.connection = connection or AsyncSupabaseConnection()

        # Cache for division_group mappings (school_name → division_group)
        self._division_group_cache: Dict[str, str] = {}
        self._cache_loaded = False

    async def _load_division_group_cache(self) -> None:
        """Load division_group mappings from baseball_rankings_data via name mapping"""
        if self._cache_loaded:
            return

        async def _load_cache_query(client: Client) -> Dict[str, str]:
            logger.info("Loading division_group cache from database...")
            result_cache: Dict[str, str] = {}

            # Get verified name mappings (school_name → team_name)
            mapping_response = client.table('school_baseball_ranking_name_mapping')\
                .select('school_name, team_name')\
                .eq('verified', True)\
                .not_.is_('team_name', 'null')\
                .execute()

            if not mapping_response.data:
                logger.warning("No verified name mappings found")
                return result_cache

            # Create team_name → school_name reverse mapping
            team_to_school = {row['team_name']: row['school_name'] for row in mapping_response.data}
            team_names = list(team_to_school.keys())

            # Get division_group for each team (most recent year's data)
            rankings_response = client.table('baseball_rankings_data')\
                .select('team_name, division_group')\
                .in_('team_name', team_names)\
                .order('year', desc=True)\
                .execute()

            if rankings_response.data:
                # Use first occurrence for each team (most recent year)
                seen_teams = set()
                for row in rankings_response.data:
                    team_name = row['team_name']
                    division_group = row.get('division_group')

                    if team_name not in seen_teams and division_group:
                        seen_teams.add(team_name)
                        school_name = team_to_school.get(team_name)
                        if school_name:
                            result_cache[school_name] = division_group

            logger.info(f"Loaded {len(result_cache)} division_group mappings into cache")
            return result_cache

        try:
            self._division_group_cache = await self.connection.execute_with_retry(_load_cache_query)
            self._cache_loaded = True
        except Exception as e:
            logger.error(f"Error loading division_group cache: {e}")
            self._cache_loaded = True  # Mark as loaded to prevent repeated failures

    async def _enrich_schools_with_division_group(self, schools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich school data with division_group from cache"""
        await self._load_division_group_cache()

        for school in schools:
            school_name = school.get('school_name')
            if school_name:
                division_group = self._division_group_cache.get(school_name)
                school['division_group'] = division_group or NON_D1  # Default to Non-D1 if not found

        return schools

    async def get_all_schools(self) -> List[Dict[str, Any]]:
        """
        Retrieve all schools from the school_data_general table, enriched with division_group

        Returns:
            List of school dictionaries with all available data including division_group
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
            schools = await self.connection.execute_with_retry(_get_all_schools_query)
            # Enrich with division_group from baseball rankings
            schools = await self._enrich_schools_with_division_group(schools)
            return schools
        except Exception as e:
            raise SchoolDataError(f"Failed to retrieve schools: {str(e)}")

    async def get_schools_by_division_group(self, division_group: str) -> List[Dict[str, Any]]:
        """
        Retrieve schools filtered by division_group

        Division group is determined by looking up via:
        school_baseball_ranking_name_mapping → baseball_rankings_data

        Args:
            division_group: The division group to filter by (e.g., "Power 4 D1", "Non-P4 D1", "Non-D1")

        Returns:
            List of school dictionaries matching the division group
        """
        try:
            # Get all schools (already enriched with division_group)
            all_schools = await self.get_all_schools()

            # Filter by division_group
            schools = [s for s in all_schools if s.get('division_group') == division_group]
            logger.info(f"Filtered to {len(schools)} schools for division group: {division_group}")
            return schools
        except Exception as e:
            raise SchoolDataError(f"Failed to retrieve schools by division group: {str(e)}")

    async def get_schools_by_division_groups(self,
                                           division_groups: List[str],
                                           limit_per_group: Optional[Dict[str, int]] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Retrieve schools from multiple division groups with optional limits per group

        Division group is determined by looking up via:
        school_baseball_ranking_name_mapping → baseball_rankings_data

        Args:
            division_groups: List of division groups to retrieve
            limit_per_group: Optional dictionary mapping division_group -> max_schools

        Returns:
            Dictionary mapping division_group -> list of schools
        """
        try:
            if not division_groups:
                return {}

            # Get all schools (already enriched with division_group)
            all_schools = await self.get_all_schools()

            # Group schools by division_group and apply limits
            results: Dict[str, List[Dict[str, Any]]] = {dg: [] for dg in division_groups}

            for school in all_schools:
                school_division = school.get('division_group')
                if school_division in division_groups:
                    # Apply limit if specified
                    limit = limit_per_group.get(school_division) if limit_per_group else None
                    if limit is None or len(results[school_division]) < limit:
                        results[school_division].append(school)

            total_schools = sum(len(schools) for schools in results.values())
            logger.info(f"Retrieved {total_schools} total schools across {len(division_groups)} division groups")
            return results
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