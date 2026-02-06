import copy

import pytest

from backend.api import preferences_router
from backend.api import async_preferences_router
from backend.utils.preferences_types import VALID_GRADES


def _base_schools():
    return [
        {"school_name": "Alpha", "scores": {"playing_time_score": 80.0, "academic_grade": "A", "nice_to_have_count": 3}},
        {"school_name": "Beta", "scores": {"playing_time_score": 65.0, "academic_grade": "B+", "nice_to_have_count": 5}},
        {"school_name": "Gamma", "scores": {"playing_time_score": 92.0, "academic_grade": "A-", "nice_to_have_count": 1}},
        {"school_name": "Delta", "scores": {"playing_time_score": None, "academic_grade": None, "nice_to_have_count": None}},
    ]


@pytest.mark.parametrize("router_mod", [preferences_router, async_preferences_router])
def test_sort_playing_time_desc(router_mod):
    schools = _base_schools()
    sorted_schools = router_mod._sort_schools(copy.deepcopy(schools), "playing_time_score", "desc")
    names = [s["school_name"] for s in sorted_schools]
    assert names[:3] == ["Gamma", "Alpha", "Beta"]
    assert names[-1] == "Delta"


@pytest.mark.parametrize("router_mod", [preferences_router, async_preferences_router])
def test_sort_playing_time_asc(router_mod):
    schools = _base_schools()
    sorted_schools = router_mod._sort_schools(copy.deepcopy(schools), "playing_time_score", "asc")
    names = [s["school_name"] for s in sorted_schools]
    assert names[:3] == ["Beta", "Alpha", "Gamma"]
    assert names[-1] == "Delta"


@pytest.mark.parametrize("router_mod", [preferences_router, async_preferences_router])
def test_sort_nice_to_have_desc(router_mod):
    schools = _base_schools()
    sorted_schools = router_mod._sort_schools(copy.deepcopy(schools), "nice_to_have_count", "desc")
    names = [s["school_name"] for s in sorted_schools]
    assert names[:3] == ["Beta", "Alpha", "Gamma"]
    assert names[-1] == "Delta"


@pytest.mark.parametrize("router_mod", [preferences_router, async_preferences_router])
def test_sort_nice_to_have_asc(router_mod):
    schools = _base_schools()
    sorted_schools = router_mod._sort_schools(copy.deepcopy(schools), "nice_to_have_count", "asc")
    names = [s["school_name"] for s in sorted_schools]
    assert names[:3] == ["Gamma", "Alpha", "Beta"]
    assert names[-1] == "Delta"


@pytest.mark.parametrize("router_mod", [preferences_router, async_preferences_router])
def test_sort_academic_grade_desc(router_mod):
    schools = _base_schools()
    sorted_schools = router_mod._sort_schools(copy.deepcopy(schools), "academic_grade", "desc")
    names = [s["school_name"] for s in sorted_schools]
    assert names[:3] == ["Alpha", "Gamma", "Beta"]  # A > A- > B+
    assert names[-1] == "Delta"


@pytest.mark.parametrize("router_mod", [preferences_router, async_preferences_router])
def test_sort_academic_grade_asc(router_mod):
    schools = _base_schools()
    sorted_schools = router_mod._sort_schools(copy.deepcopy(schools), "academic_grade", "asc")
    names = [s["school_name"] for s in sorted_schools]
    assert names[:3] == ["Beta", "Gamma", "Alpha"]
    assert names[-1] == "Delta"


@pytest.mark.parametrize("router_mod", [preferences_router, async_preferences_router])
def test_sort_academic_grade_full_order(router_mod):
    schools = []
    for idx, grade in enumerate(VALID_GRADES):
        schools.append({
            "school_name": f"S{idx}",
            "scores": {"academic_grade": grade, "playing_time_score": 50.0, "nice_to_have_count": 0}
        })
    sorted_schools = router_mod._sort_schools(copy.deepcopy(schools), "academic_grade", "desc")
    sorted_grades = [s["scores"]["academic_grade"] for s in sorted_schools]
    assert sorted_grades == VALID_GRADES


@pytest.mark.parametrize("router_mod", [preferences_router, async_preferences_router])
def test_sort_unknown_key_no_change(router_mod):
    schools = _base_schools()
    sorted_schools = router_mod._sort_schools(copy.deepcopy(schools), "unknown_key", "desc")
    assert [s["school_name"] for s in sorted_schools] == [s["school_name"] for s in schools]


@pytest.mark.parametrize("router_mod", [preferences_router, async_preferences_router])
def test_sort_missing_scores(router_mod):
    schools = [
        {"school_name": "NoScores"},
        {"school_name": "HasScores", "scores": {"playing_time_score": 70, "academic_grade": "B", "nice_to_have_count": 2}},
    ]
    sorted_schools = router_mod._sort_schools(copy.deepcopy(schools), "playing_time_score", "desc")
    assert sorted_schools[0]["school_name"] == "HasScores"
    assert sorted_schools[-1]["school_name"] == "NoScores"
