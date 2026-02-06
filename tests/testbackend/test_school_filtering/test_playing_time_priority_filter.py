import pytest

from backend.school_filtering.filters.athletic_filter import AthleticFilter
from backend.utils.preferences_types import UserPreferences


def _schools_fixture():
    return [
        {"name": "Big A", "total_athletics_grade": "A", "division": "D1"},
        {"name": "Small C", "total_athletics_grade": "C", "division": "D3"},
    ]


def test_playing_time_priority_does_not_apply_filter():
    schools = _schools_fixture()
    preferences = UserPreferences(user_state="CA")
    # Attribute is intentionally ignored by AthleticFilter (sorting happens elsewhere).
    preferences.playing_time_priority = ["High"]

    result = AthleticFilter().apply(schools, preferences)

    assert result.filter_applied is False
    assert result.schools == schools
    assert result.schools_filtered_out == 0


def test_playing_time_priority_does_not_change_min_athletics_filter():
    schools = _schools_fixture()

    prefs_without_priority = UserPreferences(user_state="CA", min_athletics_rating="B+")
    result_without_priority = AthleticFilter().apply(schools, prefs_without_priority)

    prefs_with_priority = UserPreferences(user_state="CA", min_athletics_rating="B+")
    prefs_with_priority.playing_time_priority = ["High"]
    result_with_priority = AthleticFilter().apply(schools, prefs_with_priority)

    assert result_without_priority.filter_applied is True
    assert result_with_priority.filter_applied is True
    assert result_with_priority.schools == result_without_priority.schools


def test_playing_time_priority_ignores_unknown_values():
    schools = _schools_fixture()
    preferences = UserPreferences(user_state="CA")
    preferences.playing_time_priority = ["High", "Unknown"]

    result = AthleticFilter().apply(schools, preferences)

    assert result.filter_applied is False
    assert result.schools == schools
