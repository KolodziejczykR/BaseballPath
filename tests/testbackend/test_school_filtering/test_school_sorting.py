import copy

import pytest

from backend.api import preferences_router
from backend.utils.preferences_types import VALID_GRADES
from backend.utils.recommendation_types import SchoolRecommendation, SortScores


def _rec(name, playing_time, grade, nice_count):
    return SchoolRecommendation(
        school_name=name,
        scores=SortScores(
            playing_time_score=playing_time,
            academic_grade=grade,
            nice_to_have_count=nice_count,
        ),
    )


def _base_schools():
    return [
        _rec("Alpha", 80.0, "A", 3),
        _rec("Beta", 65.0, "B+", 5),
        _rec("Gamma", 92.0, "A-", 1),
        _rec("Delta", None, None, None),
    ]


@pytest.mark.parametrize("router_mod", [preferences_router])
def test_sort_playing_time_desc(router_mod):
    schools = _base_schools()
    sorted_schools = router_mod._sort_school_recommendations(
        copy.deepcopy(schools), "playing_time_score", "desc"
    )
    names = [s.school_name for s in sorted_schools]
    assert names[:3] == ["Gamma", "Alpha", "Beta"]
    assert names[-1] == "Delta"


@pytest.mark.parametrize("router_mod", [preferences_router])
def test_sort_playing_time_asc(router_mod):
    schools = _base_schools()
    sorted_schools = router_mod._sort_school_recommendations(
        copy.deepcopy(schools), "playing_time_score", "asc"
    )
    names = [s.school_name for s in sorted_schools]
    assert names[:3] == ["Beta", "Alpha", "Gamma"]
    assert names[-1] == "Delta"


@pytest.mark.parametrize("router_mod", [preferences_router])
def test_sort_nice_to_have_desc(router_mod):
    schools = _base_schools()
    sorted_schools = router_mod._sort_school_recommendations(
        copy.deepcopy(schools), "nice_to_have_count", "desc"
    )
    names = [s.school_name for s in sorted_schools]
    assert names[:3] == ["Beta", "Alpha", "Gamma"]
    assert names[-1] == "Delta"


@pytest.mark.parametrize("router_mod", [preferences_router])
def test_sort_nice_to_have_asc(router_mod):
    schools = _base_schools()
    sorted_schools = router_mod._sort_school_recommendations(
        copy.deepcopy(schools), "nice_to_have_count", "asc"
    )
    names = [s.school_name for s in sorted_schools]
    assert names[:3] == ["Gamma", "Alpha", "Beta"]
    assert names[-1] == "Delta"


@pytest.mark.parametrize("router_mod", [preferences_router])
def test_sort_academic_grade_desc(router_mod):
    schools = _base_schools()
    sorted_schools = router_mod._sort_school_recommendations(
        copy.deepcopy(schools), "academic_grade", "desc"
    )
    names = [s.school_name for s in sorted_schools]
    assert names[:3] == ["Alpha", "Gamma", "Beta"]
    assert names[-1] == "Delta"


@pytest.mark.parametrize("router_mod", [preferences_router])
def test_sort_academic_grade_asc(router_mod):
    schools = _base_schools()
    sorted_schools = router_mod._sort_school_recommendations(
        copy.deepcopy(schools), "academic_grade", "asc"
    )
    names = [s.school_name for s in sorted_schools]
    assert names[:3] == ["Beta", "Gamma", "Alpha"]
    assert names[-1] == "Delta"


@pytest.mark.parametrize("router_mod", [preferences_router])
def test_sort_academic_grade_full_order(router_mod):
    schools = []
    for idx, grade in enumerate(VALID_GRADES):
        schools.append(_rec(f"S{idx}", 50.0, grade, 0))
    sorted_schools = router_mod._sort_school_recommendations(
        copy.deepcopy(schools), "academic_grade", "desc"
    )
    sorted_grades = [s.scores.academic_grade for s in sorted_schools]
    assert sorted_grades == VALID_GRADES


@pytest.mark.parametrize("router_mod", [preferences_router])
def test_sort_unknown_key_no_change(router_mod):
    schools = _base_schools()
    sorted_schools = router_mod._sort_school_recommendations(
        copy.deepcopy(schools), "unknown_key", "desc"
    )
    assert [s.school_name for s in sorted_schools] == [s.school_name for s in schools]


@pytest.mark.parametrize("router_mod", [preferences_router])
def test_sort_missing_scores(router_mod):
    schools = [
        SchoolRecommendation(school_name="NoScores"),
        _rec("HasScores", 70.0, "B", 2),
    ]
    sorted_schools = router_mod._sort_school_recommendations(
        copy.deepcopy(schools), "playing_time_score", "desc"
    )
    assert sorted_schools[0].school_name == "HasScores"
    assert sorted_schools[-1].school_name == "NoScores"
