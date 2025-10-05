"""
Real database integration tests with actual Supabase queries

These tests use real database connections and validate:
1. Actual data retrieval performance
2. Real filtering pipeline with full dataset
3. Database connection stability
4. Data consistency and integrity
"""

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))

import pytest
import asyncio
from typing import Dict, List, Any

from backend.school_filtering.async_two_tier_pipeline_complete import get_school_matches_shared as get_school_matches, count_eligible_schools_shared as count_eligible_schools
from backend.school_filtering.database import AsyncSchoolDataQueries
from backend.utils.preferences_types import UserPreferences
from backend.utils.prediction_types import MLPipelineResults


class TestRealDatabaseIntegration:
    """Test real database integration with actual Supabase data"""

    @pytest.mark.skipif(not os.getenv('SUPABASE_URL') or not os.getenv('SUPABASE_SERVICE_KEY'),
                       reason="Supabase credentials not available")
    @pytest.mark.asyncio
    async def test_real_database_connection(self):
        """Test that we can actually connect to Supabase"""
        queries = AsyncSchoolDataQueries()

        # Test basic connection
        try:
            # Try to get school count to verify connection
            health_check = await queries.health_check()
            assert health_check['status'] == 'healthy'
            assert health_check['school_count'] > 0
            print(f"✅ Database connection successful")
        except Exception as e:
            pytest.fail(f"Database connection failed: {e}")
        finally:
            await queries.close()

    @pytest.mark.skipif(not os.getenv('SUPABASE_URL') or not os.getenv('SUPABASE_SERVICE_KEY'),
                       reason="Supabase credentials not available")
    @pytest.mark.asyncio
    async def test_full_school_dataset_retrieval(self, query_timer):
        """Test retrieving the full school dataset"""
        queries = AsyncSchoolDataQueries()

        # Time the full dataset retrieval
        all_schools, duration, success = await query_timer.time_query_async(
            'get_all_schools',
            queries.get_all_schools
        )

        assert success, "Failed to retrieve all schools"
        assert isinstance(all_schools, list)
        assert len(all_schools) > 0, "No schools found in database"

        print(f"✅ Retrieved {len(all_schools)} schools in {duration:.3f}s")

        # Validate data structure
        if all_schools:
            first_school = all_schools[0]
            required_fields = ['school_name', 'school_state', 'division_group']
            for field in required_fields:
                assert field in first_school, f"Missing required field: {field}"

    @pytest.mark.skipif(not os.getenv('SUPABASE_URL') or not os.getenv('SUPABASE_SERVICE_KEY'),
                       reason="Supabase credentials not available")
    @pytest.mark.asyncio
    async def test_division_group_queries(self, query_timer):
        """Test querying schools by division group"""
        from backend.utils.school_group_constants import POWER_4_D1, NON_P4_D1, NON_D1

        queries = AsyncSchoolDataQueries()
        division_groups = [POWER_4_D1, NON_P4_D1, NON_D1]

        try:
            total_schools = 0
            for division in division_groups:
                schools, duration, success = await query_timer.time_query_async(
                    f'get_schools_by_division_{division.replace(" ", "_")}',
                    queries.get_schools_by_division_group,
                    division
                )

                assert success, f"Failed to get schools for {division}"
                assert isinstance(schools, list)

                print(f"✅ {division}: {len(schools)} schools ({duration:.3f}s)")
                total_schools += len(schools)

                # Validate all schools have correct division
                for school in schools[:5]:  # Check first 5
                    assert school.get('division_group') == division

            print(f"✅ Total schools across all divisions: {total_schools}")
        finally:
            await queries.close()

    @pytest.mark.skipif(not os.getenv('SUPABASE_URL') or not os.getenv('SUPABASE_SERVICE_KEY'),
                       reason="Supabase credentials not available")
    @pytest.mark.asyncio
    async def test_real_filtering_pipeline_end_to_end(self, realistic_preferences, query_timer, performance_tracker):
        """Test the complete filtering pipeline with real data"""

        for scenario in realistic_preferences:
            print(f"\n🧪 Testing scenario: {scenario['name']}")
            preferences = scenario['preferences']

            # Create realistic ML results based on preferences
            from backend.utils.player_types import PlayerInfielder
            from backend.utils.prediction_types import D1PredictionResult, P4PredictionResult

            player = PlayerInfielder(
                height=72, weight=180, exit_velo_max=90, sixty_time=7.0,
                throwing_hand='R', hitting_handedness='R', region='West',
                primary_position='SS', inf_velo=80
            )

            # Higher achieving students get better predictions
            base_d1_prob = 0.6 if preferences.gpa and preferences.gpa > 3.5 else 0.4
            base_p4_prob = 0.4 if preferences.sat and preferences.sat > 1400 else 0.2

            ml_results = MLPipelineResults(
                player=player,
                d1_results=D1PredictionResult(
                    d1_probability=base_d1_prob,
                    d1_prediction=base_d1_prob > 0.5,
                    confidence='Medium',
                    model_version='v2.1'
                ),
                p4_results=P4PredictionResult(
                    p4_probability=base_p4_prob,
                    p4_prediction=base_p4_prob > 0.5,
                    confidence='Medium',
                    is_elite=base_p4_prob > 0.6,
                    model_version='v1.3'
                )
            )

            # Test school counting
            performance_tracker.start()

            count, count_duration, count_success = await query_timer.time_query_async(
                f'count_schools_{scenario["name"]}',
                lambda p, ml: count_eligible_schools(p, ml),
                preferences, ml_results
            )

            assert count_success, f"Count failed for {scenario['name']}"
            assert isinstance(count, int)
            assert count >= 0

            # Test full matching
            result, match_duration, match_success = await query_timer.time_query_async(
                f'get_matches_{scenario["name"]}',
                lambda p, ml, l: get_school_matches(p, ml, l),
                preferences, ml_results, 50
            )

            performance_tracker.stop()

            assert match_success, f"Matching failed for {scenario['name']}"
            assert result is not None
            assert hasattr(result, 'school_matches')
            assert hasattr(result, 'must_have_count')

            print(f"  📊 Count: {count} schools ({count_duration:.3f}s)")
            print(f"  🎯 Matches: {len(result.school_matches)} schools ({match_duration:.3f}s)")
            print(f"  💾 Memory used: {performance_tracker.memory_used:.1f}MB")
            print(f"  ⏱️  Total time: {performance_tracker.duration:.3f}s")

            # Validate reasonable results
            assert count >= len(result.school_matches), "Count should be >= actual matches"
            assert len(result.school_matches) <= 50, "Should respect limit"

    @pytest.mark.skipif(not os.getenv('SUPABASE_URL') or not os.getenv('SUPABASE_SERVICE_KEY'),
                       reason="Supabase credentials not available")
    @pytest.mark.asyncio
    async def test_data_consistency_checks(self):
        """Test that database data is consistent and valid"""
        queries = AsyncSchoolDataQueries()

        try:
            # Get a sample of schools to validate
            schools = await queries.get_all_schools()

            assert len(schools) > 0, "No schools in database"
            print(f"✅ Validating {len(schools)} schools for data consistency")

            issues = []

            for school in schools:
                school_name = school.get('school_name', 'Unknown')

                # Check required fields
                required_fields = ['school_name', 'school_state', 'division_group']
                for field in required_fields:
                    if not school.get(field):
                        issues.append(f"{school_name}: Missing {field}")

                # Check data validity
                if school.get('undergrad_enrollment') is not None:
                    enrollment = school.get('undergrad_enrollment')
                    if isinstance(enrollment, (int, float)) and enrollment < 0:
                        issues.append(f"{school_name}: Negative enrollment: {enrollment}")

                if school.get('admission_rate') is not None:
                    rate = school.get('admission_rate')
                    if isinstance(rate, (int, float)) and (rate < 0 or rate > 1):
                        issues.append(f"{school_name}: Invalid admission rate: {rate}")

                # Check tuition data
                in_state = school.get('in_state_tuition')
                out_state = school.get('out_of_state_tuition')
                if in_state is not None and out_state is not None:
                    if isinstance(in_state, (int, float)) and isinstance(out_state, (int, float)):
                        if out_state < in_state:
                            issues.append(f"{school_name}: Out-of-state tuition ({out_state}) < in-state ({in_state})")

            # Report issues but don't fail unless there are too many
            if issues:
                print(f"⚠️  Found {len(issues)} data consistency issues:")
                for issue in issues[:10]:  # Show first 10
                    print(f"  - {issue}")
                if len(issues) > 10:
                    print(f"  ... and {len(issues) - 10} more")

            # Fail if more than 5% of schools have issues
            error_rate = len(issues) / len(schools)
            assert error_rate < 0.05, f"Too many data issues: {error_rate:.1%} of schools"

            print(f"✅ Data consistency check passed ({len(issues)} issues, {error_rate:.1%} error rate)")
        finally:
            await queries.close()

    @pytest.mark.skipif(not os.getenv('SUPABASE_URL') or not os.getenv('SUPABASE_SERVICE_KEY'),
                       reason="Supabase credentials not available")
    @pytest.mark.asyncio
    async def test_state_and_region_data(self):
        """Test that state and region data is valid"""
        queries = AsyncSchoolDataQueries()

        try:
            schools = await queries.get_all_schools()

            valid_states = {
                'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
                'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
                'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
                'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
                'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC'
            }

            invalid_states = []
            state_counts = {}

            for school in schools:
                state = school.get('school_state')
                if state:
                    if state not in valid_states:
                        invalid_states.append(f"{school.get('school_name')}: {state}")
                    else:
                        state_counts[state] = state_counts.get(state, 0) + 1

            if invalid_states:
                print(f"⚠️  Invalid states found:")
                for invalid in invalid_states[:5]:
                    print(f"  - {invalid}")

            assert len(invalid_states) == 0, f"Found {len(invalid_states)} schools with invalid states"

            print(f"✅ All states valid. Coverage: {len(state_counts)} states")
            print(f"  Top 5 states: {sorted(state_counts.items(), key=lambda x: x[1], reverse=True)[:5]}")
        finally:
            await queries.close()

    @pytest.mark.skipif(not os.getenv('SUPABASE_URL') or not os.getenv('SUPABASE_SERVICE_KEY'),
                       reason="Supabase credentials not available")
    @pytest.mark.asyncio
    async def test_division_group_distribution(self):
        """Test division group distribution in the database"""
        queries = AsyncSchoolDataQueries()

        try:
            from backend.utils.school_group_constants import POWER_4_D1, NON_P4_D1, NON_D1
            divisions = [POWER_4_D1, NON_P4_D1, NON_D1]

            distribution = {}
            total = 0

            for division in divisions:
                schools = await queries.get_schools_by_division_group(division)
                count = len(schools)
                distribution[division] = count
                total += count

                print(f"  {division}: {count} schools")

            print(f"✅ Total schools: {total}")

            # Validate reasonable distribution
            assert total > 0, "No schools found in any division"
            assert distribution[NON_D1] > 0, "No Non-D1 schools found"

            # Calculate percentages
            for division, count in distribution.items():
                percentage = (count / total) * 100
                print(f"  {division}: {percentage:.1f}%")
        finally:
            await queries.close()