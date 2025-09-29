"""
Two-tier school filtering pipeline

This module implements the must-have vs nice-to-have filtering system,
providing both quick counts and detailed matching results.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from backend.utils.preferences_types import UserPreferences
from backend.utils.prediction_types import MLPipelineResults
from backend.utils.school_match_types import (
    SchoolMatch, NiceToHaveMatch, NiceToHaveMiss, FilteringResult, NiceToHaveType,
    NICE_TO_HAVE_MAPPING
)
from backend.school_filtering.pipeline import SchoolFilteringPipeline
from backend.school_filtering.filters import (
    GeographicFilter, FinancialFilter, AcademicFilter,
    AthleticFilter, DemographicFilter
)

logger = logging.getLogger(__name__)


class TwoTierFilteringPipeline:
    """
    Enhanced filtering pipeline that separates must-have requirements
    from nice-to-have preferences for better UX
    """

    def __init__(self):
        self.base_pipeline = SchoolFilteringPipeline()
        self.geographic_filter = GeographicFilter()
        self.financial_filter = FinancialFilter()
        self.academic_filter = AcademicFilter()
        self.athletic_filter = AthleticFilter()
        self.demographic_filter = DemographicFilter()

    def count_must_have_matches(self, preferences: UserPreferences,
                               ml_results: MLPipelineResults) -> int:
        """
        Fast count of schools that meet must-have requirements only.
        Used for dynamic UI updates.
        If no must-haves are specified, returns total available schools.
        """
        logger.info("Counting schools that meet must-have requirements...")

        # Extract must-have preferences
        must_have_prefs = preferences.get_must_haves()

        # If no must-haves, return count of all available schools for this ML prediction
        if not must_have_prefs:
            logger.info("No must-have preferences specified, counting all available schools")
            try:
                # Create minimal preferences for just getting schools from DB
                minimal_prefs = UserPreferences(user_state=preferences.user_state)
                schools = self.base_pipeline._get_initial_schools(minimal_prefs, ml_results)
                count = len(schools) if schools else 0
                logger.info(f"Found {count} total available schools")
                return count
            except Exception as e:
                logger.error(f"Error counting all available schools: {e}")
                return 0

        try:
            # Filter by must-have requirements only
            schools = self._filter_must_haves(preferences, ml_results)
            count = len(schools) if schools else 0
            logger.info(f"Found {count} schools meeting must-have requirements")
            return count
        except Exception as e:
            logger.error(f"Error counting must-have matches: {e}")
            return 0

    def filter_with_scoring(self, preferences: UserPreferences,
                           ml_results: MLPipelineResults,
                           limit: int = 50) -> FilteringResult:
        """
        Full two-tier filtering with nice-to-have scoring.
        Returns detailed SchoolMatch objects.
        """
        logger.info("Starting two-tier filtering with nice-to-have scoring...")

        # Step 1: Filter by must-have requirements (or get all if no must-haves)
        must_have_prefs = preferences.get_must_haves()

        if not must_have_prefs:
            # No must-haves, get all available schools for scoring
            logger.info("No must-have preferences, getting all available schools")
            minimal_prefs = UserPreferences(user_state=preferences.user_state)
            must_have_schools = self.base_pipeline._get_initial_schools(minimal_prefs, ml_results)
        else:
            # Apply must-have filters
            must_have_schools = self._filter_must_haves(preferences, ml_results)

        must_have_count = len(must_have_schools) if must_have_schools else 0
        logger.info(f"Found {must_have_count} schools for detailed scoring")

        if not must_have_schools:
            return FilteringResult(
                must_have_count=0,
                school_matches=[],
                total_possible_schools=0,
                filtering_summary={"initial_schools": 0}
            )

        # Step 2: Score nice-to-have preferences for each school
        school_matches = []
        for school_data in must_have_schools:
            school_match = self._create_school_match(school_data, preferences, ml_results)
            school_matches.append(school_match)

        # Step 3: Sort by number of nice-to-have matches, then by division group alignment
        def get_division_priority(school_match):
            """Get division priority score for sorting (higher = better)"""
            ml_prediction = ml_results.get_final_prediction()
            school_division = school_match.division_group

            if school_division == ml_prediction:
                return 3  # Primary division - highest priority

            # Handle secondary divisions based on prediction type
            if ml_prediction == "Non-P4 D1":
                # Compare P4 probability vs (1-D1 probability) for tie-breaking
                d1_prob = ml_results.d1_results.d1_probability
                p4_prob = ml_results.p4_results.p4_probability if ml_results.p4_results else 0.0

                if p4_prob >= (1 - d1_prob):
                    # Power 4 is more likely than Non-D1
                    if school_division == "Power 4 D1":
                        return 2
                    elif school_division == "Non-D1":
                        return 1
                else:
                    # Non-D1 is more likely than Power 4
                    if school_division == "Non-D1":
                        return 2
                    elif school_division == "Power 4 D1":
                        return 1

            elif ml_prediction == "Non-D1":
                # Only Non-P4 D1 can be secondary
                if school_division == "Non-P4 D1":
                    return 2

            elif ml_prediction == "Power 4 D1":
                # Only Non-P4 D1 can be secondary
                if school_division == "Non-P4 D1":
                    return 2

            return 0  # Should not happen with current logic

        # Sort by: (1) nice-to-have count desc, (2) division priority desc, (3) overall grade desc
        def sort_key(school_match):
            nice_to_have_count = len(school_match.nice_to_have_matches)
            division_priority = get_division_priority(school_match)

            # Get overall grade as final tiebreaker
            overall_grade = school_match.school_data.get('overall_grade', 'F')
            from backend.utils.preferences_types import VALID_GRADES
            grade_value = VALID_GRADES.index(overall_grade) if overall_grade in VALID_GRADES else 0
            grade_value = 12 - grade_value  # Flip so A+ = 12, F = 0

            return (nice_to_have_count, division_priority, grade_value)

        school_matches.sort(key=sort_key, reverse=True)
        limited_matches = school_matches[:limit]

        logger.info(f"Scored {len(school_matches)} schools, returning top {len(limited_matches)}")

        return FilteringResult(
            must_have_count=must_have_count,
            school_matches=limited_matches,
            total_possible_schools=must_have_count,  # Could be expanded to show total in DB
            filtering_summary={
                "initial_schools": must_have_count,
                "scored_schools": len(school_matches),
                "returned_schools": len(limited_matches)
            }
        )

    def _extract_must_have_preferences(self, preferences: UserPreferences) -> Dict[str, Any]:
        """Extract only must-have preferences from UserPreferences"""
        # Use the dynamic must-have preferences from the UserPreferences object
        return preferences.get_must_haves()

    def _filter_must_haves(self, preferences: UserPreferences,
                          ml_results: MLPipelineResults) -> List[Dict[str, Any]]:
        """Apply only must-have filters"""
        # Extract must-have preferences
        must_have_prefs = preferences.get_must_haves()

        # If no must-haves, return all available schools
        if not must_have_prefs:
            minimal_prefs = UserPreferences(user_state=preferences.user_state)
            return self.base_pipeline._get_initial_schools(minimal_prefs, ml_results)

        # Create minimal preferences object for must-haves only
        # Start with required fields for proper functionality
        temp_prefs_dict = {
            'user_state': preferences.user_state
        }

        # Add all must-have preferences
        temp_prefs_dict.update(must_have_prefs)

        # Create UserPreferences object from the dictionary
        temp_prefs = UserPreferences(**temp_prefs_dict)

        # Use existing pipeline but only apply must-have filters
        schools = self.base_pipeline._get_initial_schools(temp_prefs, ml_results)

        if not schools:
            return []

        # Apply only the filters for must-have preferences
        filtered_schools = schools
        must_have_names = preferences.get_must_have_list()

        # Apply financial filter if any financial preferences are must-have
        financial_must_haves = {'max_budget'}.intersection(must_have_names)
        if financial_must_haves:
            filter_result = self.financial_filter.apply(filtered_schools, temp_prefs)
            filtered_schools = filter_result.schools

        # Apply academic filter if any academic preferences are must-have
        academic_must_haves = {'min_academic_rating', 'admit_rate_floor', 'gpa', 'sat', 'act'}.intersection(must_have_names)
        if academic_must_haves:
            filter_result = self.academic_filter.apply(filtered_schools, temp_prefs)
            filtered_schools = filter_result.schools

        # Apply geographic filter if any geographic preferences are must-have
        geographic_must_haves = {'preferred_states', 'preferred_regions'}.intersection(must_have_names)
        if geographic_must_haves:
            filter_result = self.geographic_filter.apply(filtered_schools, temp_prefs)
            filtered_schools = filter_result.schools

        # Apply athletic filter if any athletic preferences are must-have
        athletic_must_haves = {'min_athletics_rating', 'playing_time_priority'}.intersection(must_have_names)
        if athletic_must_haves:
            filter_result = self.athletic_filter.apply(filtered_schools, temp_prefs)
            filtered_schools = filter_result.schools

        # Apply demographic filter if any demographic preferences are must-have
        demographic_must_haves = {'preferred_school_size', 'party_scene_preference', 'intended_major_buckets', 'min_student_satisfaction_rating', 'hs_graduation_year'}.intersection(must_have_names)
        if demographic_must_haves:
            filter_result = self.demographic_filter.apply(filtered_schools, temp_prefs)
            filtered_schools = filter_result.schools

        return filtered_schools

    def _create_school_match(self, school_data: Dict[str, Any],
                           preferences: UserPreferences,
                           ml_results: MLPipelineResults) -> SchoolMatch:
        """Create a SchoolMatch object with nice-to-have scoring"""
        school_match = SchoolMatch(
            school_name=school_data.get('school_name', 'Unknown School'),
            school_data=school_data,
            division_group=school_data.get('division_group', 'Unknown')
        )

        # Score all nice-to-have preferences
        self._score_nice_to_haves(school_match, preferences)

        return school_match

    def _score_nice_to_haves(self, school_match: SchoolMatch, preferences: UserPreferences):
        """Score all nice-to-have preferences for a school"""
        # Use the nice-to-have preferences from UserPreferences
        nice_to_have_prefs = preferences.get_nice_to_haves()
        school_data = school_match.school_data

        logger.debug(f"Scoring nice-to-haves for {school_match.school_name}")
        logger.debug(f"Nice-to-have prefs: {list(nice_to_have_prefs.keys())}")

        for pref_name, pref_value in nice_to_have_prefs.items():
            # Skip if this preference isn't in our nice-to-have mapping
            if pref_name not in NICE_TO_HAVE_MAPPING:
                logger.debug(f"Skipping {pref_name} - not in mapping")
                continue

            # Calculate match for this preference
            nice_to_have_match = self._calculate_preference_match(
                pref_name, pref_value, school_data
            )

            if nice_to_have_match:
                logger.debug(f"Match found for {pref_name}")
                school_match.add_nice_to_have_match(nice_to_have_match)
            else:
                logger.debug(f"No match for {pref_name}")
                # Try to create a miss explanation for this preference
                nice_to_have_miss = self._calculate_preference_miss(
                    pref_name, pref_value, school_data, preferences
                )
                if nice_to_have_miss:
                    school_match.add_nice_to_have_miss(nice_to_have_miss)

        logger.debug(f"Total matches for {school_match.school_name}: {len(school_match.nice_to_have_matches)}")

    def _calculate_preference_match(self, pref_name: str, pref_value: Any,
                                  school_data: Dict[str, Any]) -> Optional[NiceToHaveMatch]:
        """Calculate how well a school matches a specific preference"""
        preference_type = NICE_TO_HAVE_MAPPING[pref_name]

        # Geographic preferences
        if pref_name == 'preferred_states':
            return self._match_preferred_states(pref_value, school_data)
        elif pref_name == 'preferred_regions':
            return self._match_preferred_regions(pref_value, school_data)

        # Academic fit
        elif pref_name == 'gpa':
            return self._match_gpa(pref_value, school_data)
        elif pref_name == 'sat':
            return self._match_sat(pref_value, school_data)
        elif pref_name == 'act':
            return self._match_act(pref_value, school_data)
        elif pref_name == 'min_academic_rating':
            return self._match_min_academic_rating(pref_value, school_data)
        elif pref_name == 'min_student_satisfaction_rating':
            return self._match_min_student_satisfaction_rating(pref_value, school_data)
        elif pref_name == 'intended_major_buckets':
            return self._match_major_buckets(pref_value, school_data)

        # School characteristics
        elif pref_name == 'preferred_school_size':
            return self._match_school_size(pref_value, school_data)
        elif pref_name == 'party_scene_preference':
            return self._match_party_scene(pref_value, school_data)

        # Athletic preferences
        elif pref_name == 'min_athletics_rating':
            return self._match_athletics_rating(pref_value, school_data)
        elif pref_name == 'playing_time_priority':
            return self._match_playing_time(pref_value, school_data)

        return None

    def _calculate_preference_miss(self, pref_name: str, pref_value: Any,
                                 school_data: Dict[str, Any], preferences: UserPreferences) -> Optional[NiceToHaveMiss]:
        """Calculate miss explanation when a preference doesn't match"""
        preference_type = NICE_TO_HAVE_MAPPING[pref_name]

        # Academic fit misses
        if pref_name == 'sat':
            return self._miss_sat(pref_value, school_data)
        elif pref_name == 'act':
            return self._miss_act(pref_value, school_data)
        elif pref_name == 'gpa':
            return self._miss_gpa(pref_value, school_data)
        elif pref_name == 'min_academic_rating':
            return self._miss_academic_rating(pref_value, school_data)
        elif pref_name == 'min_student_satisfaction_rating':
            return self._miss_student_satisfaction_rating(pref_value, school_data)
        elif pref_name == 'max_budget':
            return self._miss_max_budget(pref_value, school_data, preferences)
        elif pref_name == 'admit_rate_floor':
            return self._miss_admit_rate_floor(pref_value, school_data)

        # Geographic misses
        elif pref_name == 'preferred_states':
            return self._miss_preferred_states(pref_value, school_data)
        elif pref_name == 'preferred_regions':
            return self._miss_preferred_regions(pref_value, school_data)

        # School characteristics misses
        elif pref_name == 'preferred_school_size':
            return self._miss_school_size(pref_value, school_data)
        elif pref_name == 'party_scene_preference':
            return self._miss_party_scene(pref_value, school_data)

        # Athletic misses
        elif pref_name == 'min_athletics_rating':
            return self._miss_athletics_rating(pref_value, school_data)
        elif pref_name == 'playing_time_priority':
            return self._miss_playing_time(pref_value, school_data)

        return None

    # Specific matching methods for each preference type
    def _match_preferred_states(self, pref_states: List[str],
                               school_data: Dict[str, Any]) -> Optional[NiceToHaveMatch]:
        """Match preferred states"""
        school_state = school_data.get('school_state')  # Fixed: use correct field name
        if not school_state or not pref_states:
            return None

        if school_state in pref_states:
            return NiceToHaveMatch(
                preference_type=NiceToHaveType.GEOGRAPHIC,
                preference_name='preferred_states',
                user_value=pref_states,
                school_value=school_state,
                description=f"Located in preferred state: {school_state}"
            )
        return None

    def _match_preferred_regions(self, pref_regions: List[str],
                                school_data: Dict[str, Any]) -> Optional[NiceToHaveMatch]:
        """Match preferred regions"""
        school_region = school_data.get('school_region')  # Fixed: use correct field name
        if not school_region or not pref_regions:
            return None

        if school_region in pref_regions:
            return NiceToHaveMatch(
                preference_type=NiceToHaveType.GEOGRAPHIC,
                preference_name='preferred_regions',
                user_value=pref_regions,
                school_value=school_region,
                description=f"Located in preferred region: {school_region}"
            )
        return None

    def _match_gpa(self, user_gpa: float, school_data: Dict[str, Any]) -> Optional[NiceToHaveMatch]:
        """
        Match GPA compatibility

        TODO: Implement GPA matching
        - Database only has overall_grade, academics_grade, not GPA percentiles
        - Need to add gpa_25th_percentile and gpa_75th_percentile fields
        - Or implement mapping from grades to GPA ranges
        """
        return None  # Not implemented - no GPA percentile data in database

    def _match_school_size(self, pref_sizes: List[str],
                          school_data: Dict[str, Any]) -> Optional[NiceToHaveMatch]:
        """Match preferred school sizes"""
        enrollment = school_data.get('undergrad_enrollment')  # Fixed: use correct field name
        if not enrollment or not pref_sizes:
            return None

        # Define size categories
        size_ranges = {
            'Small': (0, 2999),
            'Medium': (3000, 9999),
            'Large': (10000, 29999),
            'Very Large': (30000, float('inf'))
        }

        # Determine school's size category
        school_size = None
        for size_name, (min_size, max_size) in size_ranges.items():
            if min_size <= enrollment <= max_size:
                school_size = size_name
                break

        if school_size and school_size in pref_sizes:
            return NiceToHaveMatch(
                preference_type=NiceToHaveType.SCHOOL_CHARACTERISTICS,
                preference_name='preferred_school_size',
                user_value=pref_sizes,
                school_value=f"{school_size} ({enrollment:,} students)",
                description=f"School size matches preference: {school_size} ({enrollment:,} students)"
            )

        return None

    def _match_min_academic_rating(self, min_rating: str, school_data: Dict[str, Any]) -> Optional[NiceToHaveMatch]:
        """Match minimum academic rating preference"""
        school_academic_rating = school_data.get('academics_grade')  # Fixed: use correct field name
        if not school_academic_rating:
            return None

        # Define grade values for comparison
        grade_values = {
            'A+': 12, 'A': 11, 'A-': 10,
            'B+': 9, 'B': 8, 'B-': 7,
            'C+': 6, 'C': 5, 'C-': 4,
            'D+': 3, 'D': 2, 'D-': 1, 'F': 0
        }

        min_value = grade_values.get(min_rating, 0)
        school_value = grade_values.get(school_academic_rating, 0)

        if school_value >= min_value:
            return NiceToHaveMatch(
                preference_type=NiceToHaveType.ACADEMIC_FIT,
                preference_name='min_academic_rating',
                user_value=min_rating,
                school_value=school_academic_rating,
                description=f"Academic rating {school_academic_rating} meets minimum {min_rating}"
            )
        return None

    def _match_min_student_satisfaction_rating(self, min_rating: str, school_data: Dict[str, Any]) -> Optional[NiceToHaveMatch]:
        """Match minimum student satisfaction rating preference"""
        school_satisfaction_rating = school_data.get('student_life_grade')
        if not school_satisfaction_rating:
            return None

        # Define grade values for comparison
        grade_values = {
            'A+': 12, 'A': 11, 'A-': 10,
            'B+': 9, 'B': 8, 'B-': 7,
            'C+': 6, 'C': 5, 'C-': 4,
            'D+': 3, 'D': 2, 'D-': 1, 'F': 0
        }

        min_value = grade_values.get(min_rating, 0)
        school_value = grade_values.get(school_satisfaction_rating, 0)

        if school_value >= min_value:
            return NiceToHaveMatch(
                preference_type=NiceToHaveType.ACADEMIC_FIT,
                preference_name='min_student_satisfaction_rating',
                user_value=min_rating,
                school_value=school_satisfaction_rating,
                description=f"Student satisfaction rating {school_satisfaction_rating} meets minimum {min_rating}"
            )
        return None

    def _act_to_sat(self, act_score: int) -> int:
        """
        Converts an ACT composite score to an approximate SAT total score
        based on official concordance tables.

        Args:
            act_score (int): The ACT composite score (typically 1-36).

        Returns:
            int or str: The approximate SAT total score, or an error message
                        if the ACT score is out of a valid range or not found.
        """
        # Official ACT to SAT concordance data (example, can be expanded)
        # Using the mid-point of the SAT range for a single value
        concordance_table = {
            36: 1600, 35: 1570, 34: 1500, 33: 1460, 32: 1430,
            31: 1400, 30: 1370, 29: 1340, 28: 1310, 27: 1270,
            26: 1240, 25: 1210, 24: 1180, 23: 1150, 22: 1120,
            21: 1090, 20: 1060, 19: 1030, 18: 990, 17: 950,
            16: 910, 15: 850, 14: 790, 13: 750, 12: 710,
            11: 670, 10: 630, 9: 590, 8: 550, 7: 510,
            6: 470, 5: 430, 4: 390, 3: 350, 2: 310, 1: 270
        }

        if not isinstance(act_score, int):
            return "Error: ACT score must be an integer."
        if not (1 <= act_score <= 36):
            return "Error: ACT score must be between 1 and 36."

        return concordance_table.get(act_score)

    def _match_sat(self, user_sat: int, school_data: Dict[str, Any]) -> Optional[NiceToHaveMatch]:
        """Match SAT score compatibility"""
        avg_sat = school_data.get('avg_sat')  # Fixed: use available field
        if not avg_sat:
            avg_act = school_data.get('avg_act')  # Fixed: use available field
            if not avg_act:
                return None
            
            avg_sat = self._act_to_sat(avg_act)

        # Simple range-based matching - within 100 points is a match
        sat_tolerance = 100

        difference = abs(user_sat - avg_sat)

        if difference <= sat_tolerance:
            if difference <= 50:
                description = f"SAT ({user_sat}) close to school average ({avg_sat})"
            else:
                description = f"SAT ({user_sat}) within range of school average ({avg_sat})"

            return NiceToHaveMatch(
                preference_type=NiceToHaveType.ACADEMIC_FIT,
                preference_name='sat',
                user_value=user_sat,
                school_value=avg_sat,
                description=description
            )
        else:
            return None  # Too far from average

    def _miss_sat(self, user_sat: int, school_data: Dict[str, Any]) -> Optional[NiceToHaveMiss]:
        """Create miss explanation for SAT score incompatibility"""
        avg_sat = school_data.get('avg_sat')
        if not avg_sat:
            avg_act = school_data.get('avg_act')
            if not avg_act:
                return None
            avg_sat = self._act_to_sat(avg_act)

        difference = abs(user_sat - avg_sat)
        sat_tolerance = 100

        # Only create miss if too far from average (beyond reasonable range)
        if difference > sat_tolerance:
            if user_sat > avg_sat:
                reason = f"SAT ({user_sat}) is significantly higher than school average ({avg_sat}) - you may be overqualified"
            else:
                reason = f"SAT ({user_sat}) is significantly lower than school average ({avg_sat}) - you may be underqualified"

            return NiceToHaveMiss(
                preference_type=NiceToHaveType.ACADEMIC_FIT,
                preference_name='sat',
                user_value=user_sat,
                school_value=avg_sat,
                reason=reason
            )

        return None

    def _sat_to_act(self, sat_score: int) -> int:
        """
        Converts an SAT total score to an approximate ACT composite score
        using a concordance table.

        Args:
            sat_score (int): The total SAT score (400-1600).

        Returns:
            int or str: The approximate ACT composite score (1-36) or an error message
                        if the input is invalid.
        """
        if not isinstance(sat_score, int) or not (400 <= sat_score <= 1600):
            return "Invalid SAT score. Please enter an integer between 400 and 1600."

        # Official concordance tables provide ranges. This dictionary maps the *lower bound*
        # of an SAT range to its corresponding ACT score.
        # The ranges are based on recent concordance data.
        concordance_table = {
            1570: 36, 1530: 35, 1490: 34, 1450: 33, 1420: 32,
            1390: 31, 1350: 30, 1320: 29, 1290: 28, 1250: 27,
            1220: 26, 1190: 25, 1150: 24, 1120: 23, 1090: 22,
            1060: 21, 1030: 20, 990: 19, 960: 18, 920: 17,
            880: 16, 830: 15, 780: 14, 730: 13, 690: 12,
            650: 11, 620: 10, 590: 9, 560: 8, 530: 7,
            500: 6, 470: 5, 440: 4, 410: 3, 400: 2 
            # Note: lowest ACT score is 1, but lowest SAT conversion is 2-3
        }

        # Find the closest matching SAT score range (iterating from highest to lowest)
        for sat_lower_bound, act_score in sorted(concordance_table.items(), reverse=True):
            if sat_score >= sat_lower_bound:
                return act_score

        # If the score is below the lowest defined range but still valid (e.g., 400-409),
        # it maps to the lowest ACT score in the table.
        return 1 # Lowest possible ACT score

    def _match_act(self, user_act: int, school_data: Dict[str, Any]) -> Optional[NiceToHaveMatch]:
        """Match ACT score compatibility"""
        avg_act = school_data.get('avg_act')  # Fixed: use available field
        if not avg_act:
            avg_sat = school_data.get('avg_sat')
            if not avg_sat:
                return None
            
            avg_act = self._sat_to_act(avg_sat)

        # Simple range-based matching - within 2 points is a match
        act_tolerance = 2

        difference = abs(user_act - avg_act)

        if difference <= act_tolerance:
            if difference <= 1:
                description = f"ACT ({user_act}) close to school average ({avg_act})"
            else:
                description = f"ACT ({user_act}) within range of school average ({avg_act})"

            return NiceToHaveMatch(
                preference_type=NiceToHaveType.ACADEMIC_FIT,
                preference_name='act',
                user_value=user_act,
                school_value=avg_act,
                description=description
            )
        else:
            return None  # Too far from average

    def _match_academic_environment(self, pref: str, school_data: Dict[str, Any]) -> Optional[NiceToHaveMatch]:
        """
        Match academic environment preference

        TODO: Implement academic environment matching
        - Need database field 'academic_environment' with values like:
          'High-academic', 'Balanced', 'Flexible'
        - Consider academic reputation, selectivity, rigor
        - May need composite scoring from multiple fields
        """
        return None  # Not implemented - no academic_environment field in database

    def _match_major_buckets(self, pref: str, school_data: Dict[str, Any]) -> Optional[NiceToHaveMatch]:
        """
        Match intended major buckets

        TODO: Implement major matching logic
        - Need database fields for available majors/programs
        - Map major buckets (Engineering, Business, etc.) to specific programs
        - Check school's program strength/availability
        - Consider program rankings if available
        """
        return None  # Not implemented - no major data in database

    def _match_party_scene(self, pref: List[str], school_data: Dict[str, Any]) -> Optional[NiceToHaveMatch]:
        """Match party scene preference with multi-select support"""
        school_party = school_data.get('party_scene_grade')
        if not school_party or not pref:
            return None

        # Map preference to rating expectations
        pref_mapping = {
            'Active': ['A+', 'A'],
            'Moderate': ['A-', 'B+', 'B'],
            'Quiet': ['B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'F']
        }

        # Check if school matches any of the selected preferences
        matched_prefs = []
        for preference in pref:
            expected_ratings = pref_mapping.get(preference, [])
            if school_party in expected_ratings:
                matched_prefs.append(preference)

        if matched_prefs:
            return NiceToHaveMatch(
                preference_type=NiceToHaveType.SCHOOL_CHARACTERISTICS,
                preference_name='party_scene_preference',
                user_value=pref,
                school_value=school_party,
                description=f"Party scene matches preferences: {', '.join(matched_prefs)} ({school_party})"
            )
        return None

    def _match_athletics_rating(self, min_rating: str, school_data: Dict[str, Any]) -> Optional[NiceToHaveMatch]:
        """Match athletics rating preference"""
        school_athletics = school_data.get('athletics_grade')  # Fixed: use correct field name
        if not school_athletics:
            return None

        # Use same grade comparison as academic rating
        grade_values = {
            'A+': 12, 'A': 11, 'A-': 10,
            'B+': 9, 'B': 8, 'B-': 7,
            'C+': 6, 'C': 5, 'C-': 4,
            'D+': 3, 'D': 2, 'D-': 1, 'F': 0
        }

        min_value = grade_values.get(min_rating, 0)
        school_value = grade_values.get(school_athletics, 0)

        if school_value >= min_value:
            return NiceToHaveMatch(
                preference_type=NiceToHaveType.ATHLETIC_PREFERENCES,
                preference_name='min_athletics_rating',
                user_value=min_rating,
                school_value=school_athletics,
                description=f"Athletics rating {school_athletics} meets minimum {min_rating}"
            )
        return None

    def _match_playing_time(self, pref: List[str], school_data: Dict[str, Any]) -> Optional[NiceToHaveMatch]:
        """
        Match playing time priority with multi-select support

        TODO: Implement playing time matching logic
        - Complex calculation requiring:
          * Current roster depth by position
          * Graduating seniors by position
          * Team's recruiting class by position
          * Competition level/difficulty
          * Coach's playing time history/philosophy
        - Need database fields for roster analysis
        - Consider ML prediction vs school's typical recruit profile
        """
        return None  # Not implemented - requires complex roster and recruiting analysis

    # Miss methods for generating CON explanations
    def _miss_preferred_states(self, pref_states: List[str], school_data: Dict[str, Any]) -> Optional[NiceToHaveMiss]:
        """Create miss explanation for preferred states"""
        school_state = school_data.get('school_state')
        if not school_state or not pref_states:
            return None

        if school_state not in pref_states:
            return NiceToHaveMiss(
                preference_type=NiceToHaveType.GEOGRAPHIC,
                preference_name='preferred_states',
                user_value=pref_states,
                school_value=school_state,
                reason=f"Located in {school_state}, not in your preferred states: {', '.join(pref_states)}"
            )
        return None

    def _miss_preferred_regions(self, pref_regions: List[str], school_data: Dict[str, Any]) -> Optional[NiceToHaveMiss]:
        """Create miss explanation for preferred regions"""
        school_region = school_data.get('school_region')
        if not school_region or not pref_regions:
            return None

        if school_region not in pref_regions:
            return NiceToHaveMiss(
                preference_type=NiceToHaveType.GEOGRAPHIC,
                preference_name='preferred_regions',
                user_value=pref_regions,
                school_value=school_region,
                reason=f"Located in {school_region} region, not in your preferred regions: {', '.join(pref_regions)}"
            )
        return None

    def _miss_school_size(self, pref_sizes: List[str], school_data: Dict[str, Any]) -> Optional[NiceToHaveMiss]:
        """Create miss explanation for school size"""
        enrollment = school_data.get('undergrad_enrollment')
        if not enrollment or not pref_sizes:
            return None

        # Define size categories
        size_ranges = {
            'Small': (0, 2999),
            'Medium': (3000, 9999),
            'Large': (10000, 29999),
            'Very Large': (30000, float('inf'))
        }

        # Determine school's size category
        school_size = None
        for size_name, (min_size, max_size) in size_ranges.items():
            if min_size <= enrollment <= max_size:
                school_size = size_name
                break

        if school_size and school_size not in pref_sizes:
            return NiceToHaveMiss(
                preference_type=NiceToHaveType.SCHOOL_CHARACTERISTICS,
                preference_name='preferred_school_size',
                user_value=pref_sizes,
                school_value=f"{school_size} ({enrollment:,} students)",
                reason=f"School size is {school_size} ({enrollment:,} students), not in your preferred sizes: {', '.join(pref_sizes)}"
            )
        return None

    def _miss_party_scene(self, pref: List[str], school_data: Dict[str, Any]) -> Optional[NiceToHaveMiss]:
        """Create miss explanation for party scene preference"""
        school_party = school_data.get('party_scene_grade')
        if not school_party or not pref:
            return None

        # Map preference to rating expectations
        pref_mapping = {
            'Active': ['A+', 'A'],
            'Moderate': ['A-', 'B+', 'B'],
            'Quiet': ['B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'F']
        }

        # Check if school matches any of the selected preferences
        matched_prefs = []
        for preference in pref:
            expected_ratings = pref_mapping.get(preference, [])
            if school_party in expected_ratings:
                matched_prefs.append(preference)

        if not matched_prefs:
            return NiceToHaveMiss(
                preference_type=NiceToHaveType.SCHOOL_CHARACTERISTICS,
                preference_name='party_scene_preference',
                user_value=pref,
                school_value=school_party,
                reason=f"Party scene ({school_party}) doesn't match your preferences: {', '.join(pref)}"
            )
        return None

    # Placeholder miss methods for other preferences
    def _miss_act(self, user_act: int, school_data: Dict[str, Any]) -> Optional[NiceToHaveMiss]:
        """Create miss explanation for ACT score incompatibility"""
        avg_act = school_data.get('avg_act')
        if not avg_act:
            avg_sat = school_data.get('avg_sat')
            if not avg_sat:
                return None
            avg_act = self._sat_to_act(avg_sat)

        difference = abs(user_act - avg_act)
        act_tolerance = 2

        # Only create miss if too far from average (beyond reasonable range)
        if difference > act_tolerance:
            if user_act > avg_act:
                reason = f"ACT ({user_act}) is significantly higher than school average ({avg_act}) - you may be overqualified"
            else:
                reason = f"ACT ({user_act}) is significantly lower than school average ({avg_act}) - you may be underqualified"

            return NiceToHaveMiss(
                preference_type=NiceToHaveType.ACADEMIC_FIT,
                preference_name='act',
                user_value=user_act,
                school_value=avg_act,
                reason=reason
            )

        return None

    def _miss_athletics_rating(self, min_rating: str, school_data: Dict[str, Any]) -> Optional[NiceToHaveMiss]:
        """Create miss explanation for athletics rating"""
        school_athletics = school_data.get('athletics_grade')
        if not school_athletics:
            return None

        # Use same grade comparison as academic rating
        grade_values = {
            'A+': 12, 'A': 11, 'A-': 10,
            'B+': 9, 'B': 8, 'B-': 7,
            'C+': 6, 'C': 5, 'C-': 4,
            'D+': 3, 'D': 2, 'D-': 1, 'F': 0
        }

        min_value = grade_values.get(min_rating, 0)
        school_value = grade_values.get(school_athletics, 0)

        if school_value < min_value:
            return NiceToHaveMiss(
                preference_type=NiceToHaveType.ATHLETIC_PREFERENCES,
                preference_name='min_athletics_rating',
                user_value=min_rating,
                school_value=school_athletics,
                reason=f"Athletics rating {school_athletics} is below your minimum requirement of {min_rating}"
            )
        return None

    def _miss_academic_rating(self, min_rating: str, school_data: Dict[str, Any]) -> Optional[NiceToHaveMiss]:
        """Create miss explanation for academic rating"""
        school_academic_rating = school_data.get('academics_grade')
        if not school_academic_rating:
            return None

        # Define grade values for comparison
        grade_values = {
            'A+': 12, 'A': 11, 'A-': 10,
            'B+': 9, 'B': 8, 'B-': 7,
            'C+': 6, 'C': 5, 'C-': 4,
            'D+': 3, 'D': 2, 'D-': 1, 'F': 0
        }

        min_value = grade_values.get(min_rating, 0)
        school_value = grade_values.get(school_academic_rating, 0)

        if school_value < min_value:
            return NiceToHaveMiss(
                preference_type=NiceToHaveType.ACADEMIC_FIT,
                preference_name='min_academic_rating',
                user_value=min_rating,
                school_value=school_academic_rating,
                reason=f"Academic rating {school_academic_rating} is below your minimum requirement of {min_rating}"
            )
        return None

    def _miss_student_satisfaction_rating(self, min_rating: str, school_data: Dict[str, Any]) -> Optional[NiceToHaveMiss]:
        """Create miss explanation for student satisfaction rating"""
        school_satisfaction_rating = school_data.get('student_life_grade')
        if not school_satisfaction_rating:
            return None

        # Define grade values for comparison
        grade_values = {
            'A+': 12, 'A': 11, 'A-': 10,
            'B+': 9, 'B': 8, 'B-': 7,
            'C+': 6, 'C': 5, 'C-': 4,
            'D+': 3, 'D': 2, 'D-': 1, 'F': 0
        }

        min_value = grade_values.get(min_rating, 0)
        school_value = grade_values.get(school_satisfaction_rating, 0)

        if school_value < min_value:
            return NiceToHaveMiss(
                preference_type=NiceToHaveType.ACADEMIC_FIT,
                preference_name='min_student_satisfaction_rating',
                user_value=min_rating,
                school_value=school_satisfaction_rating,
                reason=f"Student satisfaction rating {school_satisfaction_rating} is below your minimum requirement of {min_rating}"
            )
        return None

    def _miss_max_budget(self, max_budget: int, school_data: Dict[str, Any], preferences: UserPreferences) -> Optional[NiceToHaveMiss]:
        """Create miss explanation for budget"""
        # Use the financial filter's helper method to get correct tuition
        tuition = self.financial_filter.get_tuition(school_data, preferences)

        # If tuition data not available, return None
        if tuition is None:
            return None

        if tuition > max_budget:
            # Determine if it's in-state or out-of-state for better messaging
            if preferences.user_state:
                school_state = school_data.get('school_state', '').upper()
                user_state = preferences.user_state.upper()
                tuition_type = "in-state" if school_state == user_state else "out-of-state"
            else:
                tuition_type = "out-of-state"

            return NiceToHaveMiss(
                preference_type=NiceToHaveType.SCHOOL_CHARACTERISTICS,
                preference_name='max_budget',
                user_value=max_budget,
                school_value=tuition,
                reason=f"School {tuition_type} tuition ${tuition:,} exceeds your budget of ${max_budget:,}"
            )
        return None

    def _miss_admit_rate_floor(self, admit_rate_floor: float, school_data: Dict[str, Any]) -> Optional[NiceToHaveMiss]:
        """Create miss explanation for admission rate floor"""
        admission_rate = school_data.get('admission_rate')
        if admission_rate is None:
            return None

        # Convert percentage to decimal if needed
        admission_rate_pct = admission_rate * 100

        if admission_rate_pct < admit_rate_floor:
            return NiceToHaveMiss(
                preference_type=NiceToHaveType.ACADEMIC_FIT,
                preference_name='admit_rate_floor',
                user_value=admit_rate_floor,
                school_value=f"{admission_rate_pct:.1f}%",
                reason=f"Admission rate {admission_rate_pct:.1f}% is below your minimum of {admit_rate_floor}%"
            )
        return None

    def _miss_playing_time(self, pref: List[str], school_data: Dict[str, Any]) -> Optional[NiceToHaveMiss]:
        """Create miss explanation for playing time priority"""
        return None  # Not implemented - requires complex roster analysis
    
    def _miss_gpa(self, user_gpa: float, school_data: Dict[str, Any]) -> Optional[NiceToHaveMiss]:
        """Create miss explanation for GPA incompatibility"""
        return None  # Not implemented - no GPA percentile data


# Convenience functions for backward compatibility and ease of use
def count_eligible_schools(preferences: UserPreferences,
                          ml_results: MLPipelineResults) -> int:
    """
    Quick count of schools meeting must-have requirements.
    Perfect for dynamic UI updates.
    """
    pipeline = TwoTierFilteringPipeline()
    return pipeline.count_must_have_matches(preferences, ml_results)


def get_school_matches(preferences: UserPreferences,
                      ml_results: MLPipelineResults,
                      limit: int = 50) -> FilteringResult:
    """
    Get detailed school matches with nice-to-have scoring.
    """
    pipeline = TwoTierFilteringPipeline()
    return pipeline.filter_with_scoring(preferences, ml_results, limit)