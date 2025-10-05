"""
Async school filtering pipeline orchestrator with connection pooling and resilience
"""

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

import asyncio
import logging
from typing import List, Dict, Any, Optional

from backend.utils.preferences_types import UserPreferences
from backend.utils.prediction_types import MLPipelineResults
from backend.utils.school_group_constants import POWER_4_D1, NON_P4_D1, NON_D1
from .database import AsyncSchoolDataQueries
from .filters import (
    AcademicFilter,
    FinancialFilter,
    GeographicFilter,
    AthleticFilter,
    DemographicFilter,
    FilterResult
)
from .exceptions import FilteringError, InvalidPreferencesError, DatabaseConnectionError

# Configure logging
logger = logging.getLogger(__name__)


class AsyncSchoolFilteringPipeline:
    """
    Async main pipeline for filtering schools based on user preferences

    This class orchestrates the entire filtering process with async operations:
    1. Validates user preferences
    2. Retrieves school data from database asynchronously
    3. Applies filters in sequence
    4. Returns filtered school names for LLM processing
    """

    def __init__(self, db_queries: Optional[AsyncSchoolDataQueries] = None):
        """Initialize the async filtering pipeline"""
        self.db_queries = db_queries or AsyncSchoolDataQueries()
        self.filters = [
            GeographicFilter(),      # Apply geographic first (most restrictive)
            FinancialFilter(),       # Then financial constraints
            AcademicFilter(),        # Academic requirements
            AthleticFilter(),        # Athletic preferences
            DemographicFilter()      # Finally demographic preferences
        ]
        self.filter_results: List[FilterResult] = []

    async def filter_schools(self,
                           preferences: UserPreferences,
                           ml_results: MLPipelineResults) -> List[str]:
        """
        Main entry point for async school filtering

        Args:
            preferences: User preferences for filtering
            ml_results: ML pipeline results for division group filtering and overlap

        Returns:
            List of school names that meet all criteria

        Raises:
            InvalidPreferencesError: If preferences are invalid
            DatabaseConnectionError: If database connection fails
            FilteringError: If filtering process fails
        """
        try:
            # Reset filter results
            self.filter_results = []

            # Validate preferences
            self._validate_preferences(preferences)

            # Get initial school data (primary schools filtered by preferences + overlap schools)
            logger.info("Retrieving and filtering schools with ML-based division group selection...")
            schools = await self._get_initial_schools(preferences, ml_results)
            logger.info(f"Retrieved {len(schools)} schools (already includes preference filtering for primary group)")

            if not schools:
                logger.warning("No schools found in database")
                return []

            # Both primary and overlap schools are already filtered by preferences
            logger.info("Schools already filtered by preferences during selection process")
            filtered_schools = schools

            # Extract school names
            school_names = [school.get('school_name') for school in filtered_schools
                          if school.get('school_name')]

            # Log filtering summary
            self._log_filtering_summary(len(schools), len(school_names))

            logger.info(f"Filtering complete. {len(school_names)} schools meet all criteria")
            return school_names

        except InvalidPreferencesError:
            raise
        except DatabaseConnectionError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in filtering pipeline: {str(e)}")
            raise FilteringError(f"School filtering failed: {str(e)}")

    async def _get_initial_schools(self,
                                 preferences: UserPreferences,
                                 ml_results: MLPipelineResults) -> List[Dict[str, Any]]:
        """
        Async retrieval of initial school data based on ML predictions and preferences
        """
        try:
            # Determine the primary division group based on ML predictions
            primary_division_group = self._determine_primary_division_group(ml_results)
            logger.info(f"Primary division group: {primary_division_group}")

            # Calculate overlap divisions and their limits
            overlap_info = self._calculate_division_overlap(ml_results, primary_division_group)

            # Prepare division groups to query
            division_groups = [primary_division_group] + list(overlap_info.keys())

            # Set limits for each division group
            limits = {primary_division_group: 100}  # Primary group gets more schools
            limits.update(overlap_info)

            logger.info(f"Querying division groups: {division_groups} with limits: {limits}")

            # Get schools from multiple division groups concurrently
            schools_by_division = await self.db_queries.get_schools_by_division_groups(
                division_groups, limits
            )

            # Combine all schools
            all_schools = []
            for division_group, schools in schools_by_division.items():
                logger.info(f"Retrieved {len(schools)} schools from {division_group}")
                all_schools.extend(schools)

            logger.info(f"Total schools retrieved before preference filtering: {len(all_schools)}")

            # Apply preference filtering to all schools
            filtered_schools = await self._apply_preference_filters(all_schools, preferences)
            logger.info(f"Schools after preference filtering: {len(filtered_schools)}")

            return filtered_schools

        except Exception as e:
            logger.error(f"Error getting initial schools: {str(e)}")
            raise DatabaseConnectionError(f"Failed to retrieve schools: {str(e)}")

    async def _apply_preference_filters(self,
                                      schools: List[Dict[str, Any]],
                                      preferences: UserPreferences) -> List[Dict[str, Any]]:
        """
        Apply user preference filters to schools asynchronously
        """
        if not schools:
            return []

        # Create tasks for concurrent filtering
        filter_tasks = []

        # Break schools into chunks for concurrent processing
        chunk_size = max(1, len(schools) // 4)  # Process in 4 chunks
        school_chunks = [schools[i:i + chunk_size] for i in range(0, len(schools), chunk_size)]

        for chunk in school_chunks:
            task = asyncio.create_task(self._filter_school_chunk(chunk, preferences))
            filter_tasks.append(task)

        # Wait for all filtering tasks to complete
        filtered_chunks = await asyncio.gather(*filter_tasks, return_exceptions=True)

        # Combine results and handle any exceptions
        filtered_schools = []
        for chunk_result in filtered_chunks:
            if isinstance(chunk_result, Exception):
                logger.error(f"Filtering chunk failed: {chunk_result}")
                continue
            filtered_schools.extend(chunk_result)

        return filtered_schools

    async def _filter_school_chunk(self,
                                 school_chunk: List[Dict[str, Any]],
                                 preferences: UserPreferences) -> List[Dict[str, Any]]:
        """
        Filter a chunk of schools with preferences
        """
        filtered_chunk = school_chunk.copy()

        # Apply each filter sequentially to the chunk
        for filter_obj in self.filters:
            if not filtered_chunk:
                break

            # Apply filter (these are still sync operations, but we chunk for parallelism)
            filter_result = filter_obj.apply(filtered_chunk, preferences)
            filtered_chunk = filter_result.schools
            self.filter_results.append(filter_result)

        return filtered_chunk

    def _determine_primary_division_group(self, ml_results: MLPipelineResults) -> str:
        """
        Determine primary division group based on ML predictions
        (This logic remains the same as the sync version)
        """
        # If D1 is not predicted, go to Non-D1
        if not ml_results.d1_results.d1_prediction:
            return NON_D1

        # If D1 is predicted but no P4 results, default to Non-P4 D1
        if not ml_results.p4_results:
            return NON_P4_D1

        # If P4 is predicted, go to Power 4 D1; otherwise Non-P4 D1
        if ml_results.p4_results.p4_prediction:
            return POWER_4_D1
        else:
            return NON_P4_D1

    def _calculate_division_overlap(self, ml_results: MLPipelineResults, primary_division: str) -> Dict[str, int]:
        """
        Calculate which other division groups to include and their limits
        (This logic remains the same as the sync version)
        """
        overlap_divisions = {}

        # Get probabilities
        d1_prob = ml_results.d1_results.d1_probability
        p4_prob = ml_results.p4_results.p4_probability if ml_results.p4_results else 0.0

        if primary_division == POWER_4_D1:
            # Always include some Non-P4 D1 schools
            overlap_divisions[NON_P4_D1] = max(5, int(30 * (1 - p4_prob)))

            # Include Non-D1 if D1 confidence is not extremely high
            if d1_prob < 0.9:
                overlap_divisions[NON_D1] = max(3, int(20 * (1 - d1_prob)))

        elif primary_division == NON_P4_D1:
            # Include Power 4 D1 if P4 probability is not too low
            if p4_prob > 0.1:
                overlap_divisions[POWER_4_D1] = max(3, int(25 * p4_prob))

            # Include Non-D1 if D1 confidence is moderate
            if d1_prob < 0.8:
                overlap_divisions[NON_D1] = max(5, int(30 * (1 - d1_prob)))

        elif primary_division == NON_D1:
            # Include D1 schools if there's any reasonable probability
            if d1_prob > 0.2:
                if p4_prob > 0.3:
                    overlap_divisions[POWER_4_D1] = max(3, int(20 * p4_prob))
                overlap_divisions[NON_P4_D1] = max(5, int(25 * d1_prob))

        logger.info(f"Division overlap calculated: {overlap_divisions}")
        return overlap_divisions

    def _validate_preferences(self, preferences: UserPreferences) -> None:
        """
        Validate user preferences
        (This logic remains the same as the sync version)
        """
        if not isinstance(preferences, UserPreferences):
            raise InvalidPreferencesError("Invalid preferences object")

        if not preferences.user_state:
            raise InvalidPreferencesError("User state is required")

        # Validate state format
        if len(preferences.user_state) != 2:
            raise InvalidPreferencesError("User state must be a 2-letter state code")

        logger.debug("User preferences validated successfully")

    def _log_filtering_summary(self, initial_count: int, final_count: int) -> None:
        """
        Log a summary of the filtering process
        """
        logger.info(f"\n📊 Filtering Summary:")
        logger.info(f"  Initial schools: {initial_count}")
        logger.info(f"  Final schools: {final_count}")

        if self.filter_results:
            logger.info(f"  Filter stages applied: {len(self.filter_results)}")
            for i, result in enumerate(self.filter_results):
                logger.info(f"    Stage {i+1} ({result.filter_name}): {len(result.schools)} schools remaining")

    async def get_health_status(self) -> Dict[str, Any]:
        """
        Get health status of the async pipeline
        """
        try:
            db_health = await self.db_queries.health_check()
            return {
                'pipeline_status': 'healthy',
                'database_health': db_health,
                'filters_loaded': len(self.filters),
                'timestamp': asyncio.get_event_loop().time()
            }
        except Exception as e:
            return {
                'pipeline_status': 'unhealthy',
                'error': str(e),
                'timestamp': asyncio.get_event_loop().time()
            }

    async def close(self):
        """Clean up pipeline resources"""
        if self.db_queries:
            await self.db_queries.close()
        logger.info("Async pipeline closed")


# Global instance for dependency injection
async_pipeline = AsyncSchoolFilteringPipeline()