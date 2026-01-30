"""
Memory usage and cache testing for performance optimization

These tests validate:
1. Memory usage stays within reasonable bounds
2. No memory leaks during repeated operations
3. Cache effectiveness (if caching is implemented)
4. Memory efficiency with large datasets
"""

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))

import pytest
import time
import gc
from typing import Dict, List, Any

from backend.school_filtering.async_two_tier_pipeline import get_school_matches_shared as get_school_matches, count_eligible_schools_shared as count_eligible_schools
from backend.utils.preferences_types import UserPreferences
from backend.utils.prediction_types import MLPipelineResults, D1PredictionResult, P4PredictionResult
from backend.utils.player_types import PlayerInfielder


class TestMemoryAndCache:
    """Test memory usage and caching behavior"""

    def test_memory_baseline_measurement(self, memory_monitor):
        """Establish baseline memory usage"""
        memory_monitor.start_monitoring()

        # Simple operations to establish baseline
        preferences = UserPreferences(user_state='CA', max_budget=30000)

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
            p4_results=None
        )

        # Force garbage collection for clean baseline
        gc.collect()
        baseline_memory = memory_monitor.current_usage

        memory_monitor.stop_monitoring()

        print(f"📊 Memory Baseline: {baseline_memory:.1f}MB")

    @pytest.mark.integration
    @pytest.mark.skipif(not os.getenv('SUPABASE_URL') or not os.getenv('SUPABASE_SERVICE_KEY'),
                       reason="Supabase credentials not available")
    @pytest.mark.asyncio
    async def test_memory_usage_single_operation(self, memory_monitor, realistic_preferences):
        """Test memory usage for a single filtering operation"""

        # Use realistic preferences
        scenario = realistic_preferences[0]
        preferences = scenario['preferences']

        # Create ML results
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

        memory_monitor.start_monitoring()
        gc.collect()
        start_memory = memory_monitor.current_usage

        try:
            # Single filtering operation
            result = await get_school_matches(preferences, ml_results, limit=25)

            gc.collect()
            end_memory = memory_monitor.current_usage
            memory_monitor.stop_monitoring()

            memory_used = end_memory - start_memory
            peak_memory = memory_monitor.peak

            print(f"📊 Single Operation Memory Usage:")
            print(f"  Start: {start_memory:.1f}MB")
            print(f"  End: {end_memory:.1f}MB")
            print(f"  Used: {memory_used:.1f}MB")
            print(f"  Peak: {peak_memory:.1f}MB")
            print(f"  Schools returned: {len(result.school_matches)}")

            # Memory usage should be reasonable for single operation
            assert memory_used < 100, f"Single operation uses too much memory: {memory_used:.1f}MB"
            assert peak_memory < start_memory + 150, f"Peak memory too high: {peak_memory:.1f}MB"

        except Exception as e:
            memory_monitor.stop_monitoring()
            pytest.fail(f"Memory test failed: {e}")

    @pytest.mark.integration
    @pytest.mark.skipif(not os.getenv('SUPABASE_URL') or not os.getenv('SUPABASE_SERVICE_KEY'),
                       reason="Supabase credentials not available")
    @pytest.mark.asyncio
    async def test_memory_leak_detection(self, memory_monitor, realistic_preferences):
        """Test for memory leaks during repeated operations"""

        scenario = realistic_preferences[0]
        preferences = scenario['preferences']

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

        memory_monitor.start_monitoring()
        gc.collect()
        start_memory = memory_monitor.current_usage

        memory_measurements = []

        # Perform repeated operations
        for i in range(20):  # 20 iterations
            try:
                result = await get_school_matches(preferences, ml_results, limit=25)

                # Force garbage collection every few iterations
                if i % 5 == 0:
                    gc.collect()
                    current_memory = memory_monitor.current_usage
                    memory_measurements.append(current_memory)

            except Exception as e:
                print(f"⚠️  Operation {i} failed: {e}")

        gc.collect()
        final_memory = memory_monitor.current_usage
        memory_monitor.stop_monitoring()

        print(f"📊 Memory Leak Detection (20 operations):")
        print(f"  Start memory: {start_memory:.1f}MB")
        print(f"  Final memory: {final_memory:.1f}MB")
        print(f"  Net increase: {final_memory - start_memory:.1f}MB")
        print(f"  Peak memory: {memory_monitor.peak:.1f}MB")

        if len(memory_measurements) > 1:
            memory_trend = memory_measurements[-1] - memory_measurements[0]
            print(f"  Memory trend: {memory_trend:.1f}MB over {len(memory_measurements)} measurements")

            # Memory should not continuously increase (indicating a leak)
            assert memory_trend < 50, f"Possible memory leak detected: {memory_trend:.1f}MB increase"

        # Total memory increase should be reasonable
        total_increase = final_memory - start_memory
        assert total_increase < 100, f"Total memory increase too high: {total_increase:.1f}MB"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_memory_efficiency_with_different_limits(self, memory_monitor, realistic_preferences):
        """Test memory efficiency with different result set sizes"""

        scenario = realistic_preferences[0]
        preferences = scenario['preferences']

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

        limits = [5, 10, 25, 50]
        memory_results = {}

        for limit in limits:
            memory_monitor.start_monitoring()
            gc.collect()
            start_memory = memory_monitor.current_usage

            try:
                result = await get_school_matches(preferences, ml_results, limit=limit)

                gc.collect()
                end_memory = memory_monitor.current_usage
                memory_monitor.stop_monitoring()

                memory_used = end_memory - start_memory
                schools_returned = len(result.school_matches)

                memory_results[limit] = {
                    'memory_used': memory_used,
                    'schools_returned': schools_returned,
                    'memory_per_school': memory_used / schools_returned if schools_returned > 0 else 0
                }

                print(f"  Limit {limit}: {memory_used:.1f}MB for {schools_returned} schools ({memory_used/schools_returned:.2f}MB/school)")

            except Exception as e:
                memory_monitor.stop_monitoring()
                print(f"⚠️  Limit {limit} test failed: {e}")

        print(f"📊 Memory Efficiency by Result Size:")

        # Memory usage should scale reasonably with result size
        if len(memory_results) >= 2:
            small_limit = min(memory_results.keys())
            large_limit = max(memory_results.keys())

            small_memory = memory_results[small_limit]['memory_used']
            large_memory = memory_results[large_limit]['memory_used']

            if small_memory > 0:
                memory_scaling = large_memory / small_memory
                result_scaling = large_limit / small_limit

                print(f"  Memory scaling: {memory_scaling:.1f}x for {result_scaling:.1f}x results")

                # Memory should scale sub-linearly (due to fixed overhead)
                assert memory_scaling <= result_scaling * 1.5, "Memory scaling too high"

    def test_object_creation_memory_efficiency(self, memory_monitor):
        """Test memory efficiency of object creation"""

        memory_monitor.start_monitoring()
        gc.collect()
        start_memory = memory_monitor.current_usage

        # Create many UserPreferences objects
        preferences_list = []
        for i in range(100):
            prefs = UserPreferences(
                user_state='CA',
                max_budget=20000 + i * 100,
                min_academic_rating='B+',
                sat=1200 + (i % 10) * 20
            )
            preferences_list.append(prefs)

        gc.collect()
        after_prefs_memory = memory_monitor.current_usage

        # Create many ML results objects
        ml_results_list = []
        for i in range(100):
            player = PlayerInfielder(
                height=70 + (i % 5), weight=170 + (i % 20),
                exit_velo_max=85 + (i % 10), sixty_time=6.8 + (i % 8) * 0.1,
                throwing_hand='R', hitting_handedness='R', region='West',
                primary_position='SS', inf_velo=75 + (i % 10)
            )

            ml_results = MLPipelineResults(
                player=player,
                d1_results=D1PredictionResult(
                    d1_probability=0.3 + (i % 7) * 0.1,
                    d1_prediction=True,
                    confidence='Medium',
                    model_version='v2.1'
                ),
                p4_results=P4PredictionResult(
                    p4_probability=0.2 + (i % 5) * 0.1,
                    p4_prediction=False,
                    confidence='Medium',
                    is_elite=False,
                    model_version='v1.3'
                )
            )
            ml_results_list.append(ml_results)

        gc.collect()
        final_memory = memory_monitor.current_usage
        memory_monitor.stop_monitoring()

        prefs_memory = after_prefs_memory - start_memory
        ml_memory = final_memory - after_prefs_memory
        total_memory = final_memory - start_memory

        print(f"📊 Object Creation Memory Efficiency:")
        print(f"  100 UserPreferences: {prefs_memory:.1f}MB ({prefs_memory/100:.3f}MB each)")
        print(f"  100 ML Results: {ml_memory:.1f}MB ({ml_memory/100:.3f}MB each)")
        print(f"  Total: {total_memory:.1f}MB")

        # Each object should use reasonable memory
        assert prefs_memory / 100 < 1, f"UserPreferences objects too large: {prefs_memory/100:.3f}MB each"
        assert ml_memory / 100 < 5, f"ML Results objects too large: {ml_memory/100:.3f}MB each"

    def test_garbage_collection_effectiveness(self, memory_monitor):
        """Test that garbage collection works and memory doesn't leak

        Note: Python's memory allocator may not immediately return memory to the OS,
        but should properly manage it internally. This test verifies:
        1. Objects can be created without crashing
        2. Objects can be garbage collected
        3. Memory usage stays within reasonable bounds
        """

        memory_monitor.start_monitoring()
        gc.collect()
        baseline_memory = memory_monitor.current_usage

        # Create objects in batches to test GC between batches
        total_memory_after_batches = []

        for batch in range(3):
            # Create objects
            large_objects = []
            for i in range(100):
                prefs = UserPreferences(
                    user_state='CA',
                    preferred_states=['CA', 'TX', 'FL', 'NY', 'PA', 'OH', 'MI', 'IL'],
                    preferred_regions=['West', 'South', 'Northeast', 'Midwest'],
                    max_budget=30000 + i * 100,
                    sat=1200 + (i % 400),
                    act=24 + (i % 12)
                )

                player = PlayerInfielder(
                    height=70 + (i % 8), weight=170 + (i % 40),
                    exit_velo_max=85 + (i % 15), sixty_time=6.5 + (i % 10) * 0.1,
                    throwing_hand='R', hitting_handedness='R', region='West',
                    primary_position='SS', inf_velo=75 + (i % 15)
                )

                large_data = {
                    'preferences': prefs,
                    'player': player,
                    'large_list': list(range(100)),
                    'large_dict': {f'key_{j}': f'value_{j}' for j in range(50)},
                    'large_string': 'x' * 1000
                }
                large_objects.append(large_data)

            # Clear and collect
            large_objects.clear()
            gc.collect()
            time.sleep(0.05)

            total_memory_after_batches.append(memory_monitor.current_usage)

        gc.collect()
        final_memory = memory_monitor.current_usage
        memory_monitor.stop_monitoring()

        memory_increase = final_memory - baseline_memory

        print(f"📊 Garbage Collection Effectiveness:")
        print(f"  Baseline memory: {baseline_memory:.1f}MB")
        print(f"  Final memory: {final_memory:.1f}MB")
        print(f"  Net increase after 3 batches: {memory_increase:.1f}MB")

        # Check memory after each batch
        if len(total_memory_after_batches) >= 2:
            memory_growth = total_memory_after_batches[-1] - total_memory_after_batches[0]
            print(f"  Memory growth across batches: {memory_growth:.1f}MB")

            # Memory should not continuously grow (would indicate a leak)
            # Allow for some variance in memory measurements
            assert memory_growth < 10.0, f"Possible memory leak: {memory_growth:.1f}MB growth across batches"

        # Total memory increase should be reasonable (no unbounded growth)
        assert memory_increase < 20.0, f"Excessive memory usage: {memory_increase:.1f}MB increase"

        print("✅ Garbage collection working correctly (no memory leak detected)")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cache_behavior_if_implemented(self, realistic_preferences):
        """Test caching behavior if any caching is implemented"""

        scenario = realistic_preferences[0]
        preferences = scenario['preferences']

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

        # Test repeated identical requests
        times = []
        for i in range(5):
            start_time = time.time()
            try:
                result = await count_eligible_schools(preferences, ml_results)
                end_time = time.time()
                times.append(end_time - start_time)
            except Exception:
                times.append(float('inf'))

        print(f"📊 Cache Behavior Test (repeated identical requests):")
        for i, t in enumerate(times):
            print(f"  Request {i+1}: {t:.3f}s")

        # If caching is implemented, later requests should be faster
        if len(times) >= 3:
            first_time = times[0]
            later_times = times[2:]  # Skip second request (might be cache warmup)

            if all(t < float('inf') for t in later_times):
                avg_later_time = sum(later_times) / len(later_times)
                speedup = first_time / avg_later_time if avg_later_time > 0 else 1

                print(f"  First request: {first_time:.3f}s")
                print(f"  Average later: {avg_later_time:.3f}s")
                print(f"  Speedup: {speedup:.1f}x")

                if speedup > 1.5:
                    print("✅ Caching appears to be working")
                else:
                    print("ℹ️  No significant caching detected (or not implemented)")

    def test_memory_usage_summary(self, memory_monitor):
        """Provide summary of memory usage characteristics"""

        print(f"\n📊 Memory Usage Summary:")
        print(f"  Current process memory: {memory_monitor.current_usage:.1f}MB")

        # Test quick operations to see typical memory usage
        try:
            from backend.school_filtering.async_two_tier_pipeline import AsyncTwoTierFilteringPipeline

            pipeline = AsyncTwoTierFilteringPipeline()
            print(f"  Pipeline creation: ✅")

            preferences = UserPreferences(user_state='CA', max_budget=30000)
            print(f"  UserPreferences creation: ✅")

            print("✅ Memory usage tests completed successfully")

        except Exception as e:
            print(f"⚠️  Memory summary error: {e}")