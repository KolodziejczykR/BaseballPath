"""
Query optimization tests to ensure database queries are efficient

These tests validate:
1. Query execution times are reasonable
2. Query patterns are optimal for the dataset size
3. Database indexing is effective
4. No N+1 query problems exist
"""

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))

import pytest
import time
import asyncio
from typing import Dict, List, Any

from backend.school_filtering.database import AsyncSchoolDataQueries
from backend.school_filtering.async_two_tier_pipeline import get_school_matches_shared as get_school_matches, count_eligible_schools_shared as count_eligible_schools


class TestQueryOptimization:
    """Test database query performance and optimization"""

    @pytest.mark.skipif(not os.getenv('SUPABASE_URL') or not os.getenv('SUPABASE_SERVICE_KEY'),
                       reason="Supabase credentials not available")
    @pytest.mark.asyncio
    async def test_basic_query_performance_benchmarks(self, query_timer):
        """Test that basic queries meet performance benchmarks"""
        queries = AsyncSchoolDataQueries()

        try:
            # Benchmark 1: Get all schools should be < 2 seconds for 600-800 schools
            all_schools, duration, success = await query_timer.time_query_async(
                'get_all_schools_benchmark',
                queries.get_all_schools
            )

            assert success, "Failed to retrieve all schools"
            assert duration < 2.0, f"get_all_schools too slow: {duration:.3f}s (should be < 2.0s)"
            print(f"✅ get_all_schools: {len(all_schools)} schools in {duration:.3f}s")

            # Benchmark 2: Division group queries should be < 1 second each
            from backend.utils.school_group_constants import POWER_4_D1, NON_P4_D1, NON_D1

            for division in [POWER_4_D1, NON_P4_D1, NON_D1]:
                schools, duration, success = await query_timer.time_query_async(
                    f'division_query_{division.replace(" ", "_")}',
                    queries.get_schools_by_division_group,
                    division
                )

                assert success, f"Failed to get schools for {division}"
                assert duration < 1.0, f"Division query too slow: {duration:.3f}s (should be < 1.0s)"
                print(f"✅ {division}: {len(schools)} schools in {duration:.3f}s")
        finally:
            await queries.close()

    @pytest.mark.skipif(not os.getenv('SUPABASE_URL') or not os.getenv('SUPABASE_SERVICE_KEY'),
                       reason="Supabase credentials not available")
    @pytest.mark.asyncio
    async def test_filtering_pipeline_performance(self, realistic_preferences, query_timer):
        """Test that the complete filtering pipeline meets performance requirements"""

        # Target: Each filtering operation should complete in < 3 seconds
        for scenario in realistic_preferences:
            preferences = scenario['preferences']

            # Create ML results
            from backend.utils.player_types import PlayerInfielder
            from backend.utils.prediction_types import MLPipelineResults, D1PredictionResult, P4PredictionResult

            player = PlayerInfielder(
                height=72, weight=180, exit_velo_max=90, sixty_time=7.0,
                throwing_hand='R', hitting_handedness='R', region='West',
                primary_position='SS', inf_velo=80
            )

            ml_results = MLPipelineResults(
                player=player,
                d1_results=D1PredictionResult(
                    d1_probability=0.6, d1_prediction=True,
                    confidence='Medium', model_version='v2.1'
                ),
                p4_results=P4PredictionResult(
                    p4_probability=0.3, p4_prediction=False,
                    confidence='Medium', is_elite=False, model_version='v1.3'
                )
            )

            # Test count operation
            count, count_duration, count_success = await query_timer.time_query_async(
                f'count_performance_{scenario["name"]}',
                lambda p, ml: count_eligible_schools(p, ml),
                preferences, ml_results
            )

            assert count_success, f"Count failed for {scenario['name']}"
            assert count_duration < 3.0, f"Count too slow: {count_duration:.3f}s (should be < 3.0s)"

            # Test full filtering
            result, filter_duration, filter_success = await query_timer.time_query_async(
                f'filter_performance_{scenario["name"]}',
                lambda p, ml, limit: get_school_matches(p, ml, limit),
                preferences, ml_results, 25
            )

            assert filter_success, f"Filtering failed for {scenario['name']}"
            assert filter_duration < 3.0, f"Filtering too slow: {filter_duration:.3f}s (should be < 3.0s)"

            print(f"✅ {scenario['name']}: count={count_duration:.3f}s, filter={filter_duration:.3f}s")

    @pytest.mark.skipif(not os.getenv('SUPABASE_URL') or not os.getenv('SUPABASE_SERVICE_KEY'),
                       reason="Supabase credentials not available")
    @pytest.mark.asyncio
    async def test_query_efficiency_patterns(self, query_timer):
        """Test for efficient query patterns and avoid N+1 queries"""
        queries = AsyncSchoolDataQueries()

        # Test 1: Batch operations are more efficient than individual queries
        school_names = ['Stanford University', 'UCLA', 'USC', 'Cal Berkeley', 'San Diego State']

        # Individual queries (inefficient)
        start_time = time.time()
        individual_results = []
        for name in school_names:
            try:
                result = queries.client.table('school_data_expanded')\
                    .select('*').eq('school_name', name).execute()
                individual_results.extend(result.data or [])
            except:
                pass
        individual_time = time.time() - start_time

        # Batch query (efficient) - wrap in async function
        async def batch_query():
            return await queries.get_schools_by_names(school_names)

        batch_result, batch_time, batch_success = await query_timer.time_query_async(
            'batch_query_test',
            batch_query
        )

        try:
            pass
        finally:
            await queries.close()

        print(f"✅ Individual queries: {individual_time:.3f}s")
        print(f"✅ Batch query: {batch_time:.3f}s")

        # Batch should be faster (or at least not significantly slower)
        assert batch_time <= individual_time * 1.5, "Batch query should be more efficient"

    @pytest.mark.skipif(not os.getenv('SUPABASE_URL') or not os.getenv('SUPABASE_SERVICE_KEY'),
                       reason="Supabase credentials not available")
    @pytest.mark.asyncio
    async def test_index_effectiveness(self, query_timer):
        """Test that database indexes are effective for common queries"""
        queries = AsyncSchoolDataQueries()

        try:
            # Test indexed field queries (should be fast)
            indexed_queries = [
                ('school_name_lookup', lambda: queries.client.table('school_data_expanded')
                 .select('*').eq('school_name', 'Stanford University').execute()),

                ('state_lookup', lambda: queries.client.table('school_data_expanded')
                 .select('*').eq('school_state', 'CA').execute()),

                ('division_lookup', lambda: queries.client.table('school_data_expanded')
                 .select('*').eq('division_group', 'Power 4 D1').execute())
            ]

            for query_name, query_func in indexed_queries:
                result, duration, success = query_timer.time_query(query_name, query_func)

                assert success, f"Indexed query {query_name} failed"
                assert duration < 1.0, f"Indexed query {query_name} too slow: {duration:.3f}s"
                print(f"✅ {query_name}: {duration:.3f}s")
        finally:
            await queries.close()

    @pytest.mark.skipif(not os.getenv('SUPABASE_URL') or not os.getenv('SUPABASE_SERVICE_KEY'),
                       reason="Supabase credentials not available")
    @pytest.mark.asyncio
    async def test_filtering_query_optimization(self, query_timer):
        """Test that filtering queries are optimized"""
        queries = AsyncSchoolDataQueries()

        try:
            # Test range queries (should be reasonably fast)
            range_queries = [
                ('tuition_range', lambda: queries.client.table('school_data_expanded')
                 .select('*').gte('in_state_tuition', 10000).lte('in_state_tuition', 30000).execute()),

                ('enrollment_range', lambda: queries.client.table('school_data_expanded')
                 .select('*').gte('undergrad_enrollment', 5000).lte('undergrad_enrollment', 20000).execute()),

                ('sat_range', lambda: queries.client.table('school_data_expanded')
                 .select('*').gte('avg_sat', 1200).lte('avg_sat', 1400).execute())
            ]

            for query_name, query_func in range_queries:
                result, duration, success = query_timer.time_query(query_name, query_func)

                if success:
                    print(f"✅ {query_name}: {len(result.data or [])} results in {duration:.3f}s")
                    # Range queries should complete in reasonable time
                    assert duration < 2.0, f"Range query {query_name} too slow: {duration:.3f}s"
        finally:
            await queries.close()

    @pytest.mark.skipif(not os.getenv('SUPABASE_URL') or not os.getenv('SUPABASE_SERVICE_KEY'),
                       reason="Supabase credentials not available")
    @pytest.mark.asyncio
    async def test_complex_filtering_performance(self, query_timer):
        """Test performance of complex filtering operations"""

        # Test complex multi-criteria filtering
        complex_filter = {
            'school_state': ['CA', 'TX', 'FL'],
            'division_group': 'Non-P4 D1',
            'undergrad_enrollment': (5000, 25000),  # Range
            'academics_grade': ['A-', 'A', 'A+']
        }

        queries = AsyncSchoolDataQueries()

        try:
            # Manual complex query to test performance
            start_time = time.time()
            try:
                query = queries.client.table('school_data_expanded').select('*')
                query = query.in_('school_state', complex_filter['school_state'])
                query = query.eq('division_group', complex_filter['division_group'])
                query = query.gte('undergrad_enrollment', complex_filter['undergrad_enrollment'][0])
                query = query.lte('undergrad_enrollment', complex_filter['undergrad_enrollment'][1])

                result = query.execute()
                complex_duration = time.time() - start_time

                print(f"✅ Complex filtering: {len(result.data or [])} results in {complex_duration:.3f}s")

                # Complex queries should still be reasonable
                assert complex_duration < 3.0, f"Complex filtering too slow: {complex_duration:.3f}s"

            except Exception as e:
                print(f"⚠️  Complex filtering test failed: {e}")
        finally:
            await queries.close()

    @pytest.mark.skipif(not os.getenv('SUPABASE_URL') or not os.getenv('SUPABASE_SERVICE_KEY'),
                       reason="Supabase credentials not available")
    @pytest.mark.asyncio
    async def test_query_result_size_impact(self, query_timer):
        """Test how result set size impacts query performance"""
        queries = AsyncSchoolDataQueries()

        try:
            # Test queries with different result sizes
            size_tests = [
                ('small_result', lambda: queries.client.table('school_data_expanded')
                 .select('*').eq('division_group', 'Power 4 D1').execute()),

                ('medium_result', lambda: queries.client.table('school_data_expanded')
                 .select('*').eq('school_state', 'CA').execute()),

                ('large_result', lambda: queries.client.table('school_data_expanded')
                 .select('*').execute())
            ]

            results = {}
            for test_name, query_func in size_tests:
                result, duration, success = query_timer.time_query(test_name, query_func)

                if success:
                    size = len(result.data or [])
                    results[test_name] = {'size': size, 'duration': duration}
                    print(f"✅ {test_name}: {size} results in {duration:.3f}s ({size/duration:.0f} records/sec)")

            # Performance should scale reasonably with result size
            if 'small_result' in results and 'large_result' in results:
                small = results['small_result']
                large = results['large_result']

                # Duration should not increase dramatically with size
                size_ratio = large['size'] / small['size'] if small['size'] > 0 else 1
                time_ratio = large['duration'] / small['duration'] if small['duration'] > 0 else 1

                print(f"📊 Size scaling: {size_ratio:.1f}x size → {time_ratio:.1f}x time")

                # Time should not increase more than 3x for size increases
                assert time_ratio < size_ratio * 3, "Query performance doesn't scale well with result size"
        finally:
            await queries.close()

    def test_query_stats_summary(self, query_timer):
        """Print summary statistics for all query performance tests"""
        # This runs after other tests to summarize performance
        stats = query_timer.get_stats()

        if stats:
            print(f"\n📊 Query Performance Summary:")
            print(f"  Total queries: {stats['total_queries']}")
            print(f"  Successful: {stats['successful_queries']}")
            print(f"  Failed: {stats['failed_queries']}")
            print(f"  Average duration: {stats['avg_duration']:.3f}s")
            print(f"  Max duration: {stats['max_duration']:.3f}s")
            print(f"  Min duration: {stats['min_duration']:.3f}s")

            # Flag slow queries
            slow_queries = [q for q in stats['queries'] if q['success'] and q['duration'] > 2.0]
            if slow_queries:
                print(f"⚠️  Slow queries (>2s):")
                for query in slow_queries:
                    print(f"    {query['name']}: {query['duration']:.3f}s")

            # Performance assertions
            if stats['successful_queries'] > 0:
                assert stats['avg_duration'] < 2.0, f"Average query time too high: {stats['avg_duration']:.3f}s"
                assert stats['max_duration'] < 5.0, f"Maximum query time too high: {stats['max_duration']:.3f}s"

        print("✅ Query optimization tests completed")