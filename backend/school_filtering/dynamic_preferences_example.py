"""
Example usage of dynamic must-have preference system

This demonstrates how users can mark any preference as must-have
through the UI, and how the filtering system adapts accordingly.
"""

import os
import sys
import logging

# Suppress verbose logging for cleaner example output
logging.getLogger().setLevel(logging.WARNING)  # Only show warnings and errors
logging.getLogger('backend').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)

sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from backend.utils.preferences_types import UserPreferences
from backend.utils.prediction_types import MLPipelineResults, D1PredictionResult, P4PredictionResult
from backend.school_filtering.two_tier_pipeline import count_eligible_schools, get_school_matches
from backend.utils.player_types import PlayerInfielder


def create_sample_ml_results():
    """Create sample ML results for testing"""
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

    return MLPipelineResults(
        player=player,
        d1_results=d1_results,
        p4_results=p4_results
    )


def example_basic_must_have_functionality():
    """Demonstrate basic must-have functionality"""
    print("=" * 80)
    print("BASIC MUST-HAVE FUNCTIONALITY")
    print("=" * 80)

    # Create preferences with some values
    preferences = UserPreferences(
        user_state='CA',
        max_budget=40000,
        min_academic_rating='B+',
        preferred_states=['CA', 'TX', 'FL'],
        preferred_school_size=['Medium', 'Large'],
        gpa=3.5
    )

    print("INITIAL STATE (no mandatory must-haves):")
    print(f"Must-haves: {preferences.get_must_have_list()}")
    print(f"Must-have values: {preferences.get_must_haves()}")
    print(f"Nice-to-have values: {preferences.get_nice_to_haves()}")

    # Mark some preferences as must-have
    print(f"\nMarking 'max_budget' as must-have: {preferences.make_must_have('max_budget')}")
    print(f"Marking 'min_academic_rating' as must-have: {preferences.make_must_have('min_academic_rating')}")

    # Try to mark a None value as must-have (should fail)
    print(f"Trying to mark 'sat' (None) as must-have: {preferences.make_must_have('sat')}")

    # Try to mark invalid preference as must-have (should fail)
    print(f"Trying to mark 'invalid_pref' as must-have: {preferences.make_must_have('invalid_pref')}")

    print(f"\nAFTER MARKING:")
    print(f"Must-haves: {preferences.get_must_have_list()}")
    print(f"Must-have values: {preferences.get_must_haves()}")
    print(f"Nice-to-have values: {preferences.get_nice_to_haves()}")

    # Remove a must-have
    print(f"\nRemoving 'max_budget' from must-haves: {preferences.remove_must_have('max_budget')}")
    print(f"Removing 'user_state' (now allowed): {preferences.remove_must_have('user_state')}")

    print(f"\nFINAL STATE:")
    print(f"Must-haves: {preferences.get_must_have_list()}")
    print(f"Must-have values: {preferences.get_must_haves()}")
    print(f"Nice-to-have values: {preferences.get_nice_to_haves()}")

    print("\n" + "=" * 80)


def example_ui_simulation():
    """Simulate how the UI would work with dynamic must-haves"""
    print("UI SIMULATION - USER BUILDING PREFERENCES")
    print("=" * 80)

    ml_results = create_sample_ml_results()

    # User starts with just the required field
    preferences = UserPreferences(user_state='CA')

    print("STEP 1: User enters basic info")
    print(f"State: {preferences.user_state}")
    print(f"Must-haves: {preferences.get_must_have_list()} (none yet - everything is nice-to-have)")
    try:
        count = count_eligible_schools(preferences, ml_results)
        print(f"UI shows: '{count} schools available' (all schools since no must-haves)")
    except Exception as e:
        print(f"Count error: {e}")

    # User adds budget preference
    preferences.max_budget = 35000
    print(f"\nSTEP 2: User sets budget to ${preferences.max_budget:,}")
    print(f"Must-haves: {preferences.get_must_have_list()} (budget is nice-to-have by default)")

    try:
        count = count_eligible_schools(preferences, ml_results)
        print(f"UI shows: '{count} schools available' (no change since budget is nice-to-have)")
    except Exception as e:
        print(f"Count error: {e}")

    # User checks "Budget is must-have" checkbox
    preferences.make_must_have('max_budget')
    print(f"\nSTEP 3: User clicks 'Budget is must-have' checkbox")
    print(f"Must-haves: {preferences.get_must_have_list()}")

    try:
        count = count_eligible_schools(preferences, ml_results)
        print(f"UI shows: '{count} schools available' (count drops due to budget filter)")
    except Exception as e:
        print(f"Count error: {e}")

    # User adds more preferences
    preferences.preferred_states = ['CA', 'TX', 'FL']
    preferences.min_academic_rating = 'B+'
    preferences.gpa = 3.7

    print(f"\nSTEP 4: User adds more preferences")
    print(f"Added: preferred_states, min_academic_rating, gpa")
    print(f"Must-haves: {preferences.get_must_have_list()}")

    try:
        count = count_eligible_schools(preferences, ml_results)
        print(f"UI shows: '{count} schools available' (same count, new prefs are nice-to-have)")
    except Exception as e:
        print(f"Count error: {e}")

    # User makes academic rating must-have
    preferences.make_must_have('min_academic_rating')
    print(f"\nSTEP 5: User makes academic rating must-have")
    print(f"Must-haves: {preferences.get_must_have_list()}")

    try:
        count = count_eligible_schools(preferences, ml_results)
        print(f"UI shows: '{count} schools available' (count drops due to academic filter)")
    except Exception as e:
        print(f"Count error: {e}")

    # Show final breakdown
    print(f"\nFINAL PREFERENCE BREAKDOWN:")
    print(f"Must-have preferences: {preferences.get_must_haves()}")
    print(f"Nice-to-have preferences: {preferences.get_nice_to_haves()}")

    print("\n" + "=" * 80)


def example_detailed_filtering_with_dynamic_must_haves():
    """Show detailed filtering with user-defined must-haves"""
    print("DETAILED FILTERING WITH DYNAMIC MUST-HAVES")
    print("=" * 80)

    ml_results = create_sample_ml_results()

    # Create comprehensive preferences
    preferences = UserPreferences(
        user_state='CA',
        max_budget=40000,
        min_academic_rating='B',
        preferred_states=['CA', 'TX', 'FL'],
        preferred_regions=['West', 'South'],
        preferred_school_size=['Medium', 'Large'],
        gpa=3.5,
        sat=1350,
        party_scene_preference='Moderate',
        min_athletics_rating='B+',
        playing_time_priority='High'
    )

    # User decides what's must-have vs nice-to-have
    preferences.make_must_have('max_budget')  # Budget is critical
    preferences.make_must_have('preferred_states')  # Only wants certain states
    # Everything else stays as nice-to-have

    print("USER'S PREFERENCE CATEGORIZATION:")
    print(f"Must-haves: {list(preferences.get_must_haves().keys())}")
    print(f"Nice-to-haves: {list(preferences.get_nice_to_haves().keys())}")
    print(f"DEBUG - Internal must-have set: {preferences._must_have_preferences}")
    print(f"DEBUG - All prefs: {list(preferences.to_dict().keys())}")

    try:
        # Get must-have count
        count = count_eligible_schools(preferences, ml_results)
        print(f"\nSCHOOLS MEETING MUST-HAVES: {count}")

        # Get detailed results
        results = get_school_matches(preferences, ml_results, limit=10)

        print(f"\nDETAILED RESULTS:")
        print(f"Schools analyzed: {len(results.school_matches)}")

        for i, school_match in enumerate(results.school_matches[:5], 1):
            summary = school_match.get_match_summary()
            print(f"\n{i}. {summary['school_name']} ({summary['division_group']})")
            print(f"   Overall Nice-to-Have Match: {summary['overall_match_percentage']}%")
            print(f"   Matches {summary['total_nice_to_have_matches']} nice-to-have preferences")

            # Show top matches
            if summary['top_matches']:
                print("   Top matches:")
                for match in summary['top_matches'][:3]:
                    print(f"     • {match['description']}")

    except Exception as e:
        print(f"Error: {e}")

    print("\n" + "=" * 80)


def example_api_integration():
    """Show how this would work with API requests"""
    print("API INTEGRATION EXAMPLE")
    print("=" * 80)

    print("FRONTEND TO BACKEND COMMUNICATION:")
    print("\n1. USER CREATES PREFERENCES ON FRONTEND:")

    preferences = UserPreferences(
        user_state='TX',
        max_budget=30000,
        min_academic_rating='B+',
        preferred_states=['TX', 'CA'],
        gpa=3.4
    )

    # User marks some as must-have via UI checkboxes
    preferences.make_must_have('max_budget')
    preferences.make_must_have('min_academic_rating')

    print("   Preferences with must-have markings created")

    print("\n2. FRONTEND SENDS TO BACKEND:")
    api_data = preferences.to_dict_with_must_haves()
    print(f"   POST /api/schools/filter")
    print(f"   Body: {api_data}")

    print("\n3. BACKEND PROCESSES PREFERENCES:")
    print("   - Separates must-haves from nice-to-haves")
    print("   - Applies hard filters for must-haves")
    print("   - Scores nice-to-haves for ranking")

    print("\n4. FOR REAL-TIME COUNTING (as user types):")
    print("   - Frontend calls GET /api/schools/count")
    print("   - Backend returns just the count of must-have matches")
    print("   - UI updates: '23 schools meet your requirements'")

    print("\n5. RECONSTRUCTING PREFERENCES FROM API:")
    # Simulate receiving data from API
    received_data = api_data.copy()
    must_have_list = received_data.pop('must_have_preferences', [])

    # Reconstruct preferences
    new_prefs = UserPreferences(**{k: v for k, v in received_data.items() if v is not None})
    failed_must_haves = new_prefs.set_must_haves_from_list(must_have_list)

    print(f"   Reconstructed must-haves: {new_prefs.get_must_have_list()}")
    if failed_must_haves:
        print(f"   Failed to set as must-have: {failed_must_haves}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    """Run all examples"""
    try:
        example_basic_must_have_functionality()
        example_ui_simulation()
        example_detailed_filtering_with_dynamic_must_haves()
        example_api_integration()
    except Exception as e:
        print(f"Error running examples: {e}")
        import traceback
        traceback.print_exc()