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
from typing import List, Dict, Any, Optional, Tuple
from supabase import Client

from .async_connection import AsyncSupabaseConnection
from ..exceptions import SchoolDataError
from backend.utils.school_group_constants import NON_D1, NON_P4_D1, POWER_4_D1

logger = logging.getLogger(__name__)


class AsyncSchoolDataQueries:
    """Async database query operations for school data with resilience patterns

    Division group is stored in baseball_rankings_data, accessed via:
    school_data_general.school_name → school_baseball_ranking_name_mapping.team_name → baseball_rankings_data.division_group
    """

    def __init__(self, connection: Optional[AsyncSupabaseConnection] = None):
        self.connection = connection or AsyncSupabaseConnection()

        # Cache for baseball enrichment mappings (school_name → enrichment payload)
        self._division_group_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_loaded = False

    @staticmethod
    def _normalize_school_name(name: str) -> str:
        if not isinstance(name, str):
            return ""
        return " ".join(name.strip().lower().split())

    @staticmethod
    def _normalize_division_group(value: Any) -> str:
        if not value:
            return NON_D1
        normalized = str(value).strip()
        lowered = normalized.lower()

        if lowered in {"power 4 d1", "power4 d1", "p4", "power 4"}:
            return POWER_4_D1
        if lowered in {"non-p4 d1", "non p4 d1"}:
            return NON_P4_D1
        if lowered in {"non-d1", "non d1", "d2", "d3"}:
            return NON_D1
        if lowered in {"d1", "division 1", "division i"}:
            return NON_P4_D1
        if "power" in lowered and "4" in lowered:
            return POWER_4_D1
        if "non-p4" in lowered or "non p4" in lowered:
            return NON_P4_D1
        if "non-d1" in lowered or "non d1" in lowered:
            return NON_D1

        return normalized

    @staticmethod
    def _chunk_list(items: List[str], chunk_size: int = 500) -> List[List[str]]:
        """Split a list into deterministic chunks for large .in_ queries."""
        if not items:
            return []
        return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]

    @staticmethod
    def _coerce_division_number(value: Any) -> Optional[int]:
        """Coerce a division value into 1/2/3 when possible."""
        if value is None:
            return None

        try:
            as_int = int(value)
            if as_int in (1, 2, 3):
                return as_int
        except (TypeError, ValueError):
            pass

        text = str(value).strip().lower()
        if not text:
            return None

        if any(token in text for token in ("d1", "division 1", "division i", "ncaa i")):
            return 1
        if any(token in text for token in ("d2", "division 2", "division ii", "ncaa ii")):
            return 2
        if any(token in text for token in ("d3", "division 3", "division iii", "ncaa iii")):
            return 3

        return None

    def _derive_division_group(self, division_group: Any, division: Any) -> str:
        """
        Normalize division_group with division fallback.
        If division_group is missing but division=1, default to Non-P4 D1 (never Non-D1).
        """
        if division_group:
            return self._normalize_division_group(division_group)

        division_num = self._coerce_division_number(division)
        if division_num == 1:
            return NON_P4_D1
        if division_num in (2, 3):
            return NON_D1
        return NON_D1

    @staticmethod
    def _calculate_division_percentile(overall_rating: Optional[float], ratings: List[float]) -> Optional[float]:
        """
        Calculate percentile where higher is better.
        For Massey-style ratings (lower is better), percentile is based on teams with worse ratings.
        """
        if overall_rating is None or not ratings:
            return None

        try:
            position = sum(1 for rating in ratings if rating > overall_rating)
            return round((position / len(ratings)) * 100, 1)
        except Exception:
            return None

    async def _load_division_group_cache(self) -> None:
        """Load baseball enrichment mappings from baseball_rankings_data via name mapping."""
        if self._cache_loaded:
            return

        async def _load_cache_query(client: Client) -> Dict[str, Dict[str, Any]]:
            logger.info("Loading division_group + baseball metrics cache from database...")
            result_cache: Dict[str, Dict[str, Any]] = {}

            # Prefer verified mappings, then gracefully fall back if a project has not marked them.
            mapping_response = (
                client.table("school_baseball_ranking_name_mapping")
                .select("school_name, team_name, verified")
                .eq("verified", True)
                .not_.is_("team_name", "null")
                .execute()
            )
            mapping_rows = mapping_response.data or []

            if not mapping_rows:
                logger.warning("No verified mappings found; falling back to non-false mappings")
                fallback_response = (
                    client.table("school_baseball_ranking_name_mapping")
                    .select("school_name, team_name, verified")
                    .neq("verified", False)
                    .not_.is_("team_name", "null")
                    .execute()
                )
                mapping_rows = fallback_response.data or []

            if not mapping_rows:
                logger.warning("No non-false mappings found; falling back to any non-null team_name mapping")
                fallback_any_response = (
                    client.table("school_baseball_ranking_name_mapping")
                    .select("school_name, team_name, verified")
                    .not_.is_("team_name", "null")
                    .execute()
                )
                mapping_rows = fallback_any_response.data or []

            if not mapping_rows:
                logger.warning("No name mappings found in school_baseball_ranking_name_mapping")
                return result_cache

            # Create team_name → [school_name, ...] reverse mapping
            team_to_school: Dict[str, List[str]] = {}
            for row in mapping_rows:
                team_name = (row.get("team_name") or "").strip()
                school_name = (row.get("school_name") or "").strip()
                if not team_name or not school_name:
                    continue
                if team_name not in team_to_school:
                    team_to_school[team_name] = []
                team_to_school[team_name].append(school_name)

            if not team_to_school:
                logger.warning("Name mapping query returned rows, but none had usable team_name + school_name")
                return result_cache

            team_names = list(team_to_school.keys())
            latest_by_team: Dict[str, Dict[str, Any]] = {}

            for team_chunk in self._chunk_list(team_names):
                try:
                    rankings_response = (
                        client.table("baseball_rankings_data")
                        .select(
                            "team_name, year, division, division_group, "
                            "overall_rating, offensive_rating, defensive_rating"
                        )
                        .in_("team_name", team_chunk)
                        .order("year", desc=True)
                        .execute()
                    )
                except Exception as e:
                    logger.warning(f"Failed ordering rankings by year for chunk; retrying without order: {e}")
                    rankings_response = (
                        client.table("baseball_rankings_data")
                        .select(
                            "team_name, year, division, division_group, "
                            "overall_rating, offensive_rating, defensive_rating"
                        )
                        .in_("team_name", team_chunk)
                        .execute()
                    )

                for row in rankings_response.data or []:
                    team_name = (row.get("team_name") or "").strip()
                    if not team_name:
                        continue

                    existing = latest_by_team.get(team_name)
                    if existing is None:
                        latest_by_team[team_name] = row
                        continue

                    new_year = row.get("year") or 0
                    existing_year = existing.get("year") or 0
                    if new_year > existing_year:
                        latest_by_team[team_name] = row
                        continue

                    if (
                        new_year == existing_year
                        and not existing.get("division_group")
                        and row.get("division_group")
                    ):
                        latest_by_team[team_name] = row

            if not latest_by_team:
                logger.warning("No rankings rows found for mapped team names")
                return result_cache

            # Preload rating distributions for percentile calculation.
            year_div_pairs = {
                (row.get("year"), row.get("division"))
                for row in latest_by_team.values()
                if row.get("year") is not None and row.get("division") is not None
            }
            ratings_by_year_div: Dict[Tuple[int, int], List[float]] = {}

            for year, division in year_div_pairs:
                response = (
                    client.table("baseball_rankings_data")
                    .select("overall_rating")
                    .eq("year", year)
                    .eq("division", division)
                    .not_.is_("overall_rating", "null")
                    .execute()
                )
                ratings = sorted(
                    [
                        record.get("overall_rating")
                        for record in (response.data or [])
                        if record.get("overall_rating") is not None
                    ]
                )
                ratings_by_year_div[(year, division)] = ratings

            for team_name, row in latest_by_team.items():
                schools = team_to_school.get(team_name) or []
                if not schools:
                    continue

                division_group = self._derive_division_group(
                    row.get("division_group"),
                    row.get("division")
                )
                year = row.get("year")
                division = self._coerce_division_number(row.get("division"))
                overall_rating = row.get("overall_rating")
                ratings = ratings_by_year_div.get((year, row.get("division")), [])
                division_percentile = self._calculate_division_percentile(overall_rating, ratings)

                enrichment_payload = {
                    "division_group": division_group,
                    "baseball_team_name": team_name,
                    "baseball_rankings_year": year,
                    "baseball_division": division,
                    "baseball_overall_rating": overall_rating,
                    "baseball_offensive_rating": row.get("offensive_rating"),
                    "baseball_defensive_rating": row.get("defensive_rating"),
                    "baseball_division_percentile": division_percentile,
                }

                for school_name in schools:
                    result_cache[school_name] = enrichment_payload
                    normalized_key = self._normalize_school_name(school_name)
                    if normalized_key:
                        result_cache[normalized_key] = enrichment_payload

            logger.info(f"Loaded {len(result_cache)} school enrichment mappings into cache")
            return result_cache

        try:
            self._division_group_cache = await self.connection.execute_with_retry(_load_cache_query)
            self._cache_loaded = True
        except Exception as e:
            logger.error(f"Error loading division_group cache: {e}")
            # Keep cache unloadable state so future calls can retry.
            self._cache_loaded = False

    async def _enrich_schools_with_division_group(self, schools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich school data with division_group and baseball metrics from cache."""
        await self._load_division_group_cache()

        for school in schools:
            school_name = school.get('school_name')
            existing_division_group = school.get('division_group')

            enrichment_payload: Optional[Dict[str, Any]] = None
            if school_name:
                enrichment_payload = self._division_group_cache.get(school_name)
                if not enrichment_payload:
                    normalized_key = self._normalize_school_name(school_name)
                    enrichment_payload = self._division_group_cache.get(normalized_key)

            if enrichment_payload:
                school['division_group'] = self._normalize_division_group(
                    enrichment_payload.get("division_group")
                )
                for key, value in enrichment_payload.items():
                    if key == "division_group":
                        continue
                    if value is not None:
                        school[key] = value
            elif existing_division_group:
                school['division_group'] = self._normalize_division_group(existing_division_group)
            else:
                # Preserve old fallback behavior when neither cache nor source column has a value.
                school['division_group'] = NON_D1

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
