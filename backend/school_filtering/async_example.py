"""
Async example usage of the two-tier school filtering system

This demonstrates how to use the async must-have vs nice-to-have filtering
for both quick counts (UI updates) and detailed matching with connection pooling.
"""

import os
import sys
import asyncio
import logging

# Suppress verbose logging for cleaner example output
logging.getLogger().setLevel(logging.WARNING)  # Only show warnings and errors
logging.getLogger('backend').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)

sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from backend.utils.preferences_types import UserPreferences
from backend.utils.prediction_types import MLPipelineResults, D1PredictionResult, P4PredictionResult
from backend.school_filtering.async_two_tier_pipeline_complete import count_eligible_schools_shared, get_school_matches_shared
from backend.utils.player_types import PlayerInfielder


async def example_dynamic_counting():
    """Example of async dynamic school counting for UI"""
    print("=" * 80)
    print("ASYNC DYNAMIC SCHOOL COUNTING EXAMPLE")
    print("=" * 80)

    # Start with minimal preferences
    preferences = UserPreferences(
        user_state='CA'  # Only required field
    )

    # Create sample ML results
    player = PlayerInfielder(
        height=72, weight=180, exit_velo_max=95, sixty_time=6.8,
        throwing_hand='R', hitting_handedness='R', region='West',
        primary_position='SS', inf_velo=85
    )

    d1_results = D1PredictionResult(
        d1_probability=0.78,
        d1_prediction=True,
        confidence='High',
        model_version='v2.1'
    )

    p4_results = P4PredictionResult(
        p4_probability=0.35,
        p4_prediction=False,
        confidence='Medium',
        is_elite=False,
        model_version='v1.3'
    )

    ml_results = MLPipelineResults(
        player=player,
        d1_results=d1_results,
        p4_results=p4_results
    )

    # Show how count changes as must-have preferences are added
    scenarios = [
        ("No must-haves", UserPreferences(user_state='CA')),
        ("Budget as must-have", UserPreferences(user_state='CA', max_budget=40000)),
        ("Budget + Academic as must-haves", UserPreferences(user_state='CA', max_budget=40000, min_academic_rating='B+')),
        ("Budget + Academic + States as must-haves", UserPreferences(user_state='CA', max_budget=40000, min_academic_rating='B+', preferred_states=['CA', 'TX']))
    ]

    # Mark the appropriate preferences as must-have for each scenario
    scenario_configs = [
        [],  # No must-haves
        ['max_budget'],  # Budget only
        ['max_budget', 'min_academic_rating'],  # Budget + Academic
        ['max_budget', 'min_academic_rating', 'preferred_states']  # Budget + Academic + States
    ]

    for (scenario_name, prefs), must_have_list in zip(scenarios, scenario_configs):
        # Mark preferences as must-have
        for pref_name in must_have_list:
            prefs.make_must_have(pref_name)

        try:
            count = await count_eligible_schools_shared(prefs, ml_results)
            print(f"\n{scenario_name}: {count} eligible schools")

            # Show the dynamic must-have preferences
            print(f"  Must-have preferences: {prefs.get_must_haves()}")

        except Exception as e:
            print(f"  Error: {e}")

    print("\n" + "=" * 80)


async def example_detailed_matching():
    """Example of async detailed school matching with nice-to-have scoring"""
    print("ASYNC DETAILED MATCHING WITH NICE-TO-HAVE SCORING")
    print("=" * 80)

    # Create comprehensive preferences
    preferences = UserPreferences(
        # Must-haves
        user_state='CA',
        max_budget=35000,
        min_academic_rating='B',

        # Nice-to-haves
        preferred_states=['CA', 'TX', 'FL'],
        preferred_regions=['West', 'South'],
        preferred_school_size=['Medium', 'Large'],
        gpa=3.5,
        sat=1350,
        intended_major_buckets='Engineering',
        party_scene_preference=['Moderate'],
        min_athletics_rating='B+',
        playing_time_priority=['High'],
    )

    # Create ML results
    player = PlayerInfielder(
        height=74, weight=190, exit_velo_max=98, sixty_time=6.5,
        throwing_hand='R', hitting_handedness='L', region='West',
        primary_position='3B', inf_velo=88
    )

    d1_results = D1PredictionResult(
        d1_probability=0.85,
        d1_prediction=True,
        confidence='High',
        model_version='v2.1'
    )

    p4_results = P4PredictionResult(
        p4_probability=0.45,
        p4_prediction=False,
        confidence='Medium',
        is_elite=False,
        model_version='v1.3'
    )

    ml_results = MLPipelineResults(
        player=player,
        d1_results=d1_results,
        p4_results=p4_results
    )

    # Mark some preferences as must-have for demonstration
    preferences.make_must_have('max_budget')
    preferences.make_must_have('min_academic_rating')
    preferences.make_must_have('preferred_states')

    try:
        # Get detailed matching results with async processing
        filtering_result = await get_school_matches_shared(preferences, ml_results)

        print(f"\nASYNC FILTERING SUMMARY:")
        print(f"  • Schools meeting must-haves: {filtering_result.must_have_count}")
        print(f"  • Schools with detailed scoring: {len(filtering_result.school_matches)}")
        print(f"  • Total schools considered: {filtering_result.total_schools_considered}")

        print(f"\nMUST-HAVE PREFERENCES:")
        must_haves = preferences.get_must_haves()
        for key, value in must_haves.items():
            print(f"  • {key}: {value}")

        print(f"\nNICE-TO-HAVE PREFERENCES:")
        nice_to_haves = preferences.get_nice_to_haves()
        for key, value in nice_to_haves.items():
            print(f"  • {key}: {value}")

        print(f"\nTOP MATCHING SCHOOLS:")
        print(f"ML Prediction: {ml_results.get_final_prediction()}")

        for i, school_match in enumerate(filtering_result.school_matches[:5], 1):  # Show top 5
            summary = school_match.get_match_summary()
            print(f"\n{i}. {summary['school_name']} ({summary['division_group']})")
            print(f"   Nice-to-have Matches: {summary['total_nice_to_have_matches']}")

            # Show PROs (matched preferences)
            if summary['pros']:
                print("   PROs (What matches your preferences):")
                for match in summary['pros'][:3]:  # Show top 3 pros
                    print(f"     ✓ {match['description']}")

            # Show CONs (missed preferences)
            if summary['cons']:
                print("   CONs (What doesn't match your preferences):")
                for miss in summary['cons'][:3]:  # Show top 3 cons
                    print(f"     ✗ {miss['reason']}")

    except Exception as e:
        print(f"Error: {e}")

    print("\n" + "=" * 80)


async def example_ui_integration():
    """Example showing how async pipeline would integrate with UI"""
    print("ASYNC UI INTEGRATION EXAMPLE")
    print("=" * 80)

    print("This is how the frontend would use the async two-tier system:")
    print("\n1. USER STARTS FILLING PREFERENCES:")
    print("   - As they add must-haves, call await count_eligible_schools_shared()")
    print("   - Update UI: 'X schools match your requirements'")

    print("\n2. USER CLICKS 'SEE MATCHES':")
    print("   - Call await get_school_matches_shared() for detailed results")
    print("   - Show schools sorted by nice-to-have match percentage")

    print("\n3. FRONTEND API ENDPOINTS NEEDED:")
    print("   - GET /api/schools/count?user_state=CA&max_budget=40000")
    print("   - GET /api/schools/matches (with full preferences in body)")

    print("\n4. ASYNC BENEFITS:")
    print("   - Connection pooling reduces database load")
    print("   - Concurrent processing speeds up batch operations")
    print("   - Better error handling and resilience")
    print("   - Improved scalability under load")

    # Simulate the user experience with async operations
    base_prefs = UserPreferences(user_state='TX')

    player = PlayerInfielder(
        height=70, weight=175, exit_velo_max=92, sixty_time=7.0,
        throwing_hand='R', hitting_handedness='R', region='South',
        primary_position='2B', inf_velo=82
    )

    ml_results = MLPipelineResults(
        player=player,
        d1_results=D1PredictionResult(0.65, True, 'Medium', 'v2.1'),
        p4_results=P4PredictionResult(0.25, False, 'Medium', False, 'v1.3')
    )

    print(f"\nASYNC SIMULATED USER EXPERIENCE:")

    try:
        # Step 1: Just state
        count1 = await count_eligible_schools_shared(base_prefs, ml_results)
        print(f"  User selects TX → '{count1} schools available'")

        # Step 2: Add budget (make it must-have)
        prefs2 = UserPreferences(user_state='TX', max_budget=30000)
        prefs2.make_must_have('max_budget')
        count2 = await count_eligible_schools_shared(prefs2, ml_results)
        print(f"  User sets $30k budget as must-have → '{count2} schools available'")

        # Step 3: Add academic requirement (make it must-have)
        prefs3 = UserPreferences(user_state='TX', max_budget=30000, min_academic_rating='B+')
        prefs3.make_must_have('max_budget')
        prefs3.make_must_have('min_academic_rating')
        count3 = await count_eligible_schools_shared(prefs3, ml_results)
        print(f"  User requires B+ academics as must-have → '{count3} schools available'")

        print(f"\n  User clicks 'Show Me Schools' → async detailed matches with scoring")

        # Show async performance benefit
        import time
        start_time = time.time()
        detailed_result = await get_school_matches_shared(prefs3, ml_results, limit=10)
        end_time = time.time()

        print(f"  Async processing completed in {end_time - start_time:.2f}s")
        print(f"  Found {len(detailed_result.school_matches)} schools with detailed analysis")

    except Exception as e:
        print(f"  Simulation error: {e}")

    print("\n" + "=" * 80)


async def example_concurrent_operations():
    """Example demonstrating concurrent async operations"""
    print("CONCURRENT ASYNC OPERATIONS EXAMPLE")
    print("=" * 80)

    # Create different user scenarios
    scenarios = [
        UserPreferences(user_state='CA', max_budget=25000),
        UserPreferences(user_state='TX', max_budget=35000, min_academic_rating='B+'),
        UserPreferences(user_state='FL', max_budget=45000, preferred_school_size=['Large']),
    ]

    # Mark must-haves for each scenario
    scenarios[0].make_must_have('max_budget')
    scenarios[1].make_must_have('max_budget')
    scenarios[1].make_must_have('min_academic_rating')
    scenarios[2].make_must_have('max_budget')
    scenarios[2].make_must_have('preferred_school_size')

    # Create sample ML results
    player = PlayerInfielder(
        height=72, weight=180, exit_velo_max=93, sixty_time=6.9,
        throwing_hand='R', hitting_handedness='R', region='West',
        primary_position='SS', inf_velo=84
    )

    ml_results = MLPipelineResults(
        player=player,
        d1_results=D1PredictionResult(0.75, True, 'High', 'v2.1'),
        p4_results=P4PredictionResult(0.30, False, 'Medium', False, 'v1.3')
    )

    print("Running concurrent count operations for multiple scenarios...")

    try:
        import time
        start_time = time.time()

        # Run all count operations concurrently
        count_tasks = [
            count_eligible_schools_shared(prefs, ml_results) for prefs in scenarios
        ]

        counts = await asyncio.gather(*count_tasks)

        end_time = time.time()

        print(f"\nConcurrent operations completed in {end_time - start_time:.2f}s")

        for i, (prefs, count) in enumerate(zip(scenarios, counts), 1):
            print(f"  Scenario {i} ({prefs.user_state}): {count} schools")

        print("\nThis demonstrates how async operations can run concurrently,")
        print("improving performance when handling multiple users simultaneously.")

    except Exception as e:
        print(f"Error in concurrent operations: {e}")

    print("\n" + "=" * 80)


async def main():
    """Run all async examples"""
    try:
        await example_dynamic_counting()
        await example_detailed_matching()
        await example_ui_integration()
        await example_concurrent_operations()

        print("All async examples completed successfully!")

    except Exception as e:
        print(f"Error running async examples: {e}")


if __name__ == "__main__":
    """Run all examples with asyncio"""
    asyncio.run(main())