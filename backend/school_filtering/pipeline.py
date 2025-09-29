"""
Main school filtering pipeline orchestrator
"""

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from typing import List, Dict, Any, Optional
import logging

from backend.utils.preferences_types import UserPreferences
from backend.utils.prediction_types import MLPipelineResults
from backend.utils.school_group_constants import POWER_4_D1, NON_P4_D1, NON_D1
from .database import SchoolDataQueries
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
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SchoolFilteringPipeline:
    """
    Main pipeline for filtering schools based on user preferences

    This class orchestrates the entire filtering process:
    1. Validates user preferences
    2. Retrieves school data from database
    3. Applies filters in sequence
    4. Returns filtered school names for LLM processing
    """

    def __init__(self):
        """Initialize the filtering pipeline"""
        self.db_queries = SchoolDataQueries()
        self.filters = [
            GeographicFilter(),      # Apply geographic first (most restrictive)
            FinancialFilter(),       # Then financial constraints
            AcademicFilter(),        # Academic requirements
            AthleticFilter(),        # Athletic preferences
            DemographicFilter()      # Finally demographic preferences
        ]
        self.filter_results: List[FilterResult] = []

    def filter_schools(self,
                      preferences: UserPreferences,
                      ml_results: MLPipelineResults) -> List[str]:
        """
        Main entry point for school filtering

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
            schools = self._get_initial_schools(preferences, ml_results)
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

        except Exception as e:
            logger.error(f"Error in filtering pipeline: {str(e)}")
            if isinstance(e, (InvalidPreferencesError, DatabaseConnectionError, FilteringError)):
                raise
            else:
                raise FilteringError(f"Unexpected error in filtering pipeline: {str(e)}")

    def get_filtering_summary(self) -> Dict[str, Any]:
        """
        Get summary of filtering process

        Returns:
            Dictionary with filtering statistics and results
        """
        summary = {
            "total_filters_applied": len([r for r in self.filter_results if r.filter_applied]),
            "filters": []
        }

        for result in self.filter_results:
            filter_info = {
                "filter_name": result.filter_name,
                "applied": result.filter_applied,
                "schools_remaining": len(result.schools),
                "schools_filtered_out": result.schools_filtered_out,
                "reason": result.reason
            }
            summary["filters"].append(filter_info)

        return summary

    def _validate_preferences(self, preferences: UserPreferences) -> None:
        """
        Validate user preferences

        Args:
            preferences: User preferences to validate

        Raises:
            InvalidPreferencesError: If preferences are invalid
        """
        if not isinstance(preferences, UserPreferences):
            raise InvalidPreferencesError("Invalid preferences object")

        # Additional validation could be added here
        # The UserPreferences class already has built-in validation

    def _get_initial_schools(self, preferences: UserPreferences, ml_results: MLPipelineResults) -> List[Dict[str, Any]]:
        """
        Get initial set of schools from database, filtered by ML predictions with probability overlap

        Args:
            preferences: User preferences (may influence initial query)
            ml_results: ML results to filter by division group with probability-based overlap

        Returns:
            List of school dictionaries

        Raises:
            DatabaseConnectionError: If database query fails
        """
        try:
            # Get schools using probability-based selection
            return self._get_schools_with_probability_overlap(ml_results, preferences)

        except Exception as e:
            raise DatabaseConnectionError(f"Failed to retrieve schools: {str(e)}")

    def _get_schools_with_probability_overlap(self, ml_results: MLPipelineResults, preferences: UserPreferences) -> List[Dict[str, Any]]:
        """
        Get schools with improved probability-based selection

        Process:
        1. Get ALL schools that match must-haves from each division group
        2. Find all nice-to-haves for all schools
        3. Use ML probabilities to determine how many schools from each division to include
           - Non-D1: Can go UP to Non-P4 D1 (based on D1 probability)
           - Non-P4 D1: Can go BOTH directions - UP to Power 4 D1 (P4 prob) AND DOWN to Non-D1 (1-D1 prob)
           - Power 4 D1: Can go DOWN to Non-P4 D1 (based on 1-P4 probability)
        4. Select top schools by nice-to-have count (with overall_grade tiebreaker) from each group

        Args:
            ml_results: ML pipeline results with probabilities
            preferences: User preferences for filtering

        Returns:
            Combined list of top schools from each division group based on probabilities
        """
        from backend.school_filtering.two_tier_pipeline import TwoTierFilteringPipeline

        final_prediction = ml_results.get_final_prediction()
        d1_probability = ml_results.d1_results.d1_probability
        p4_probability = ml_results.p4_results.p4_probability if ml_results.p4_results else 0.0

        logger.info(f"Getting schools with improved probability logic for: {final_prediction}")
        logger.info(f"D1 probability: {d1_probability:.3f}, P4 probability: {p4_probability:.3f}")

        # Step 1: Get ALL schools that match must-haves from each division group
        all_division_groups = [NON_D1, NON_P4_D1, POWER_4_D1]
        division_schools = {}

        for division in all_division_groups:
            schools = self.db_queries.get_schools_by_division_group(division)
            filtered_schools = self._apply_filters(schools, preferences)
            division_schools[division] = filtered_schools
            logger.info(f"Found {len(filtered_schools)} {division} schools that meet must-haves")

        # Step 2: Calculate how many schools to take from each division based on ML probabilities
        primary_count = len(division_schools[final_prediction])

        if primary_count == 0:
            logger.warning("No schools qualify in primary division group")
            return []

        # Calculate limits for each division based on prediction and probabilities
        division_limits = {division: 0 for division in all_division_groups}
        division_limits[final_prediction] = primary_count  # Take all primary schools

        if final_prediction == NON_D1:
            # Can only go UP to Non-P4 D1
            division_limits[NON_P4_D1] = int(primary_count * d1_probability)

        elif final_prediction == NON_P4_D1:
            # Can go BOTH directions (only prediction that can do this)
            division_limits[POWER_4_D1] = int(primary_count * p4_probability)
            division_limits[NON_D1] = int(primary_count * (1 - d1_probability))

        elif final_prediction == POWER_4_D1:
            # Can only go DOWN to Non-P4 D1
            division_limits[NON_P4_D1] = int(primary_count * (1 - p4_probability))

        logger.info(f"Division limits: {division_limits}")

        # Step 3: For each division, calculate nice-to-haves and select top schools
        final_schools = []
        two_tier_pipeline = TwoTierFilteringPipeline()

        for division, limit in division_limits.items():
            if limit == 0:
                continue

            available_schools = division_schools[division]

            if len(available_schools) <= limit:
                # Take all available schools
                final_schools.extend(available_schools)
                logger.info(f"Added all {len(available_schools)} {division} schools")
            else:
                # Need to select top schools by nice-to-have count + overall_grade tiebreaker
                scored_schools = []

                for school_data in available_schools:
                    school_match = two_tier_pipeline._create_school_match(school_data, preferences, ml_results)
                    nice_to_have_count = len(school_match.nice_to_have_matches)
                    overall_grade = school_data.get('overall_grade', 'F')

                    # Convert grade to numeric for sorting (A+ = 12, F = 0)
                    from backend.utils.preferences_types import VALID_GRADES
                    grade_value = VALID_GRADES.index(overall_grade) if overall_grade in VALID_GRADES else 0
                    grade_value = 12 - grade_value  # Flip so A+ = 12, F = 0

                    scored_schools.append({
                        'school_data': school_data,
                        'nice_to_have_count': nice_to_have_count,
                        'grade_value': grade_value
                    })

                # Sort by nice-to-have count (desc), then by grade value (desc)
                scored_schools.sort(key=lambda x: (x['nice_to_have_count'], x['grade_value']), reverse=True)

                # Take top schools
                selected_schools = [item['school_data'] for item in scored_schools[:limit]]
                final_schools.extend(selected_schools)

                logger.info(f"Selected top {len(selected_schools)} {division} schools (from {len(available_schools)} available)")

        logger.info(f"Total schools selected: {len(final_schools)}")
        return final_schools

    def _apply_filters(self,
                      schools: List[Dict[str, Any]],
                      preferences: UserPreferences) -> List[Dict[str, Any]]:
        """
        Apply all filters in sequence

        Args:
            schools: Initial list of schools
            preferences: User preferences

        Returns:
            Filtered list of schools
        """
        current_schools = schools

        for filter_obj in self.filters:
            logger.info(f"Applying {filter_obj.filter_name}...")

            result = filter_obj.apply(current_schools, preferences)
            self.filter_results.append(result)

            if result.filter_applied:
                logger.info(f"{filter_obj.filter_name}: {result.schools_filtered_out} schools filtered out, "
                          f"{len(result.schools)} remaining")
                current_schools = result.schools
            else:
                logger.info(f"{filter_obj.filter_name}: Skipped - {result.reason}")

        return current_schools

    def _apply_final_filters(self, schools: List[Dict[str, Any]], preferences: UserPreferences) -> List[Dict[str, Any]]:
        """
        Apply preference filters only to overlap schools (primary schools already filtered)

        Note: This method identifies overlap schools and applies filters only to them,
        keeping all primary schools unchanged.

        Args:
            schools: Combined list of primary (already filtered) + overlap (unfiltered) schools
            preferences: User preferences for filtering

        Returns:
            List with all primary schools + filtered overlap schools
        """
        # TODO: Better way to identify which schools are primary vs overlap
        # For now, apply filters to all schools but this will double-filter primary schools
        # This is acceptable for now since primary schools should pass filters anyway

        logger.info("Applying filters to combined school list (primary + overlap)")
        return self._apply_filters(schools, preferences)


    def _log_filtering_summary(self, initial_count: int, final_count: int) -> None:
        """
        Log summary of filtering process

        Args:
            initial_count: Number of schools before filtering
            final_count: Number of schools after filtering
        """
        logger.info("="*50)
        logger.info("FILTERING SUMMARY")
        logger.info("="*50)
        logger.info(f"Initial schools: {initial_count}")

        for result in self.filter_results:
            if result.filter_applied:
                logger.info(f"{result.filter_name}: -{result.schools_filtered_out} schools")
            else:
                logger.info(f"{result.filter_name}: Skipped ({result.reason})")

        logger.info(f"Final schools: {final_count}")

        if initial_count > 0:
            reduction_pct = ((initial_count - final_count) / initial_count) * 100
            logger.info(f"Reduction: {reduction_pct:.1f}%")

        logger.info("="*50)


def filter_schools_for_llm(preferences: UserPreferences,
                          ml_results: MLPipelineResults) -> List[str]:
    """
    Convenience function for filtering schools

    Args:
        preferences: User preferences
        ml_results: ML pipeline results for division group filtering

    Returns:
        List of school names suitable for LLM processing
    """
    pipeline = SchoolFilteringPipeline()
    return pipeline.filter_schools(preferences, ml_results)