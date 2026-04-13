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
from backend.evaluation.competitiveness import (
    DEFAULT_DIVISION_MAX_RANKS,
    compute_school_sci_from_rankings,
    rank_to_percentile,
)
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

    @staticmethod
    def _is_power_four_conference(conference: Any) -> bool:
        if conference is None:
            return False

        normalized = str(conference).strip().lower()
        if not normalized:
            return False

        power_four_tokens = (
            "acc",
            "atlantic coast",
            "sec",
            "southeastern",
            "big ten",
            "b1g",
            "big 12",
            "pac-12",
            "pac 12",
            "pac12",
        )
        return any(token in normalized for token in power_four_tokens)

    def _derive_division_group(self, division_group: Any, division: Any, conference: Any = None) -> str:
        """
        Normalize division_group with division fallback.
        If division_group is missing but division=1, infer Power 4 from conference, otherwise Non-P4 D1.
        """
        division_num = self._coerce_division_number(division)
        is_power_four = self._is_power_four_conference(conference)

        if division_group:
            normalized_group = self._normalize_division_group(division_group)
            if normalized_group == NON_P4_D1 and division_num == 1 and is_power_four:
                return POWER_4_D1
            return normalized_group

        if division_num == 1:
            if is_power_four:
                return POWER_4_D1
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

            # Include all mappings that have a team_name.
            # The verified column has no false values; all rows are NULL or TRUE.
            mapping_rows: List[Dict[str, Any]] = []
            try:
                mapping_response = (
                    client.table("school_baseball_ranking_name_mapping")
                    .select("school_name, team_name, verified")
                    .not_.is_("team_name", "null")
                    .execute()
                )
                mapping_rows = mapping_response.data or []
            except Exception as exc:
                logger.warning("Non-false mapping query failed, falling back: %s", exc)

            if not mapping_rows:
                logger.warning("No non-false mappings found; falling back to any non-null team_name mapping")
                try:
                    fallback_any_response = (
                        client.table("school_baseball_ranking_name_mapping")
                        .select("school_name, team_name, verified")
                        .not_.is_("team_name", "null")
                        .execute()
                    )
                    mapping_rows = fallback_any_response.data or []
                except Exception as exc:
                    logger.warning("Mapping query with verified column failed, retrying without verified: %s", exc)
                    fallback_no_verified_response = (
                        client.table("school_baseball_ranking_name_mapping")
                        .select("school_name, team_name")
                        .not_.is_("team_name", "null")
                        .execute()
                    )
                    mapping_rows = fallback_no_verified_response.data or []

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
            target_years = {"2023", "2024", "2025"}
            rows_by_team_year: Dict[str, Dict[str, Dict[str, Any]]] = {}
            max_rank_by_year_div_metric: Dict[Tuple[str, str, str], float] = {}

            for team_chunk in self._chunk_list(team_names):
                try:
                    rankings_response = (
                        client.table("baseball_rankings_data")
                        .select(
                            "team_name, year, division, division_group, "
                            "overall_rating, offensive_rating, defensive_rating, "
                            "power_rating, strength_of_schedule"
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
                            "overall_rating, offensive_rating, defensive_rating, "
                            "power_rating, strength_of_schedule"
                        )
                        .in_("team_name", team_chunk)
                        .execute()
                    )

                for row in rankings_response.data or []:
                    team_name = (row.get("team_name") or "").strip()
                    year_val = row.get("year")
                    if not team_name or year_val is None:
                        continue

                    try:
                        year_key = str(int(year_val))
                    except (TypeError, ValueError):
                        continue

                    if year_key not in target_years:
                        continue

                    per_team_year = rows_by_team_year.setdefault(team_name, {})
                    existing_year_row = per_team_year.get(year_key)
                    if (
                        existing_year_row is None
                        or (not existing_year_row.get("division_group") and row.get("division_group"))
                    ):
                        per_team_year[year_key] = row

                    division_num = self._coerce_division_number(row.get("division"))
                    if division_num not in (1, 2, 3):
                        continue

                    division_key = str(division_num)
                    for metric in (
                        "overall_rating",
                        "offensive_rating",
                        "defensive_rating",
                        "power_rating",
                    ):
                        metric_value = row.get(metric)
                        if metric_value is None:
                            continue
                        try:
                            metric_float = float(metric_value)
                        except (TypeError, ValueError):
                            continue
                        cache_key = (year_key, division_key, metric)
                        max_rank_by_year_div_metric[cache_key] = max(
                            metric_float,
                            max_rank_by_year_div_metric.get(cache_key, 0.0),
                        )

            if not rows_by_team_year:
                logger.warning("No rankings rows found for mapped team names")
                return result_cache

            latest_by_team: Dict[str, Dict[str, Any]] = {}
            for team_name, by_year in rows_by_team_year.items():
                if not by_year:
                    continue
                latest_row = max(
                    by_year.values(),
                    key=lambda entry: int(entry.get("year") or 0),
                )
                latest_by_team[team_name] = latest_row

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
                year_key = str(int(year)) if year is not None else None
                max_rank = None
                if year_key and division in (1, 2, 3):
                    max_rank = max_rank_by_year_div_metric.get((year_key, str(division), "overall_rating"))
                    if not max_rank or max_rank <= 1:
                        max_rank = DEFAULT_DIVISION_MAX_RANKS.get(str(division))
                division_percentile = rank_to_percentile(overall_rating, max_rank) if max_rank else None
                if division_percentile is not None:
                    division_percentile = round(division_percentile, 1)

                school_sci = compute_school_sci_from_rankings(
                    rows_by_team_year.get(team_name, {}),
                    max_ranks_by_year_div_metric=max_rank_by_year_div_metric,
                )
                yearly_overall = school_sci.get("yearly_overall_national") or {}
                rounded_yearly_overall = {
                    year_key: (round(value, 2) if value is not None else None)
                    for year_key, value in yearly_overall.items()
                }

                enrichment_payload = {
                    "division_group": division_group,
                    "baseball_team_name": team_name,
                    "baseball_rankings_year": year,
                    "baseball_division": division,
                    "baseball_overall_rating": overall_rating,
                    "baseball_offensive_rating": row.get("offensive_rating"),
                    "baseball_defensive_rating": row.get("defensive_rating"),
                    "baseball_power_rating": row.get("power_rating"),
                    "baseball_strength_of_schedule": row.get("strength_of_schedule"),
                    "baseball_division_percentile": division_percentile,
                    "baseball_sci_hitter": (
                        round(school_sci["sci_hitter"], 2)
                        if school_sci.get("sci_hitter") is not None
                        else None
                    ),
                    "baseball_sci_pitcher": (
                        round(school_sci["sci_pitcher"], 2)
                        if school_sci.get("sci_pitcher") is not None
                        else None
                    ),
                    "baseball_trend_bonus": round(float(school_sci.get("trend_bonus") or 0.0), 2),
                    "baseball_sci_overall_weighted": (
                        round(school_sci["overall_weighted"], 2)
                        if school_sci.get("overall_weighted") is not None
                        else None
                    ),
                    "baseball_sci_offensive_weighted": (
                        round(school_sci["offensive_weighted"], 2)
                        if school_sci.get("offensive_weighted") is not None
                        else None
                    ),
                    "baseball_sci_defensive_weighted": (
                        round(school_sci["defensive_weighted"], 2)
                        if school_sci.get("defensive_weighted") is not None
                        else None
                    ),
                    "baseball_sci_power_weighted": (
                        round(school_sci["power_weighted"], 2)
                        if school_sci.get("power_weighted") is not None
                        else None
                    ),
                    "baseball_sci_yearly_overall": rounded_yearly_overall,
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
            fallback_division = (
                school.get("division")
                or school.get("baseball_division")
                or school.get("ncaa_division")
                or school.get("athletic_division")
            )
            fallback_conference = (
                school.get("conference")
                or school.get("athletic_conference")
                or school.get("baseball_conference")
                or school.get("conference_name")
            )

            enrichment_payload: Optional[Dict[str, Any]] = None
            if school_name:
                enrichment_payload = self._division_group_cache.get(school_name)
                if not enrichment_payload:
                    normalized_key = self._normalize_school_name(school_name)
                    enrichment_payload = self._division_group_cache.get(normalized_key)

            if enrichment_payload:
                school['division_group'] = self._derive_division_group(
                    enrichment_payload.get("division_group"),
                    enrichment_payload.get("baseball_division") or fallback_division,
                    fallback_conference,
                )
                for key, value in enrichment_payload.items():
                    if key == "division_group":
                        continue
                    if value is not None:
                        school[key] = value
            else:
                school['division_group'] = self._derive_division_group(
                    existing_division_group,
                    fallback_division,
                    fallback_conference,
                )

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
