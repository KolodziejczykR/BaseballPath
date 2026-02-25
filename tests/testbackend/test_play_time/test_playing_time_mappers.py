"""Mapper tests for school-to-playing-time context conversion."""

from backend.playing_time.mappers import school_data_to_context


def test_school_data_to_context_uses_nested_rankings_fields():
    school_data = {
        "school_name": "Arizona State University",
        "division_group": "Power 4 D1",
        "conference": "Big 12",
    }
    baseball_strength = {
        "has_data": True,
        "current_season": {
            "division_percentile": 88.2,
        },
        "weighted_averages": {
            "weighted_offensive_rating": 21.5,
            "weighted_defensive_rating": 18.7,
        },
        "trend_analysis": {
            "trend": "declining",
            "change": 5.4,
            "years_span": "2023-2025",
        },
    }

    context = school_data_to_context(school_data, baseball_strength)

    assert context.division == 1
    assert context.is_power_4 is True
    assert context.division_percentile == 88.2
    assert context.offensive_rating == 21.5
    assert context.defensive_rating == 18.7
    assert context.trend == "declining"
    assert context.trend_change == 5.4
    assert context.trend_years == "2023-2025"


def test_school_data_to_context_parses_non_d1_as_non_d1_division():
    school_data = {
        "school_name": "Example Non-D1 School",
        "division_group": "Non-D1",
    }

    context = school_data_to_context(school_data, baseball_strength=None)

    # Non-D1 should not be treated as D1 by default.
    assert context.division == 2
    assert context.get_division_group() == "D2"


def test_school_data_to_context_uses_school_enrichment_fallbacks():
    school_data = {
        "school_name": "Harvard University",
        "division_group": "Non-P4 D1",
        "baseball_offensive_rating": 120.0,
        "baseball_defensive_rating": 141.0,
        "baseball_division_percentile": 72.5,
        "baseball_program_trend": "improving",
        "baseball_trend_change": -4.3,
        "baseball_trend_years": "2023-2025",
    }

    context = school_data_to_context(school_data, baseball_strength=None)

    assert context.division == 1
    assert context.is_power_4 is False
    assert context.division_percentile == 72.5
    assert context.offensive_rating == 120.0
    assert context.defensive_rating == 141.0
    assert context.trend == "improving"
    assert context.trend_change == -4.3
    assert context.trend_years == "2023-2025"
