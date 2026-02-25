from types import SimpleNamespace

import importlib
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure project root is importable when running this file in isolation.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.api.main import app
from backend.utils.school_match_types import SchoolMatch, NiceToHaveMatch, NiceToHaveType
from backend.utils.recommendation_types import PlayingTimeInfo


def _get_preferences_module():
    """Import the live preferences router module used by the FastAPI app."""
    for module_name in ("api.routers.preferences", "backend.api.routers.preferences"):
        try:
            return importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
    raise ModuleNotFoundError("Could not import preferences router module")


def _make_school_match(name, division_group, academic_grade, playing_time_percentile, nice_to_have_count):
    school_data = {
        "school_name": name,
        "school_state": "CA",
        "school_region": "West",
        "undergrad_enrollment": 8000,
        "academics_grade": academic_grade,
        "avg_sat": 1200,
        "avg_act": 26,
        "admission_rate": 0.5,
        "total_athletics_grade": "B",
        "student_life_grade": "B",
        "party_scene_grade": "B",
        "in_state_tuition": 20000,
        "out_of_state_tuition": 35000,
        "overall_grade": "B+",
    }

    matches = [
        NiceToHaveMatch(
            preference_type=NiceToHaveType.GEOGRAPHIC,
            preference_name=f"pref_{i}",
            user_value="X",
            school_value="Y",
            description="match",
        )
        for i in range(nice_to_have_count)
    ]

    return SchoolMatch(
        school_name=name,
        school_data=school_data,
        division_group=division_group,
        nice_to_have_matches=matches,
        nice_to_have_misses=[],
        playing_time_result=SimpleNamespace(percentile=playing_time_percentile),
    )


def _mock_filtering_result(school_matches):
    return SimpleNamespace(
        school_matches=school_matches,
        must_have_count=len(school_matches),
        total_schools_considered=len(school_matches),
    )


def _base_request(sort_by=None, sort_order="desc"):
    payload = {
        "user_preferences": {
            "user_state": "CA",
        },
        "player_info": {
            "height": 72,
            "weight": 180,
            "primary_position": "SS",
            "exit_velo_max": 90.0,
            "sixty_time": 7.0,
            "inf_velo": 80.0,
            "throwing_hand": "R",
            "hitting_handedness": "R",
            "region": "West",
        },
        "ml_results": {
            "d1_results": {
                "d1_probability": 0.7,
                "d1_prediction": True,
                "confidence": "High",
                "model_version": "v1",
            }
        },
    }
    if sort_by:
        payload["sort_by"] = sort_by
        payload["sort_order"] = sort_order
    return payload


def _patch_preferences_router(monkeypatch, matches):
    pref_mod = _get_preferences_module()

    async def _mock_get_school_matches_shared(preferences, ml_results, limit):
        return _mock_filtering_result(matches)

    monkeypatch.setattr(
        pref_mod,
        "get_school_matches_shared",
        _mock_get_school_matches_shared,
    )
    monkeypatch.setattr(
        pref_mod,
        "_format_playing_time",
        lambda _: PlayingTimeInfo(available=False),
    )


def test_preferences_filter_sort_by_playing_time(monkeypatch):
    matches = [
        _make_school_match("A", "Non-P4 D1", "B", 70.0, 2),
        _make_school_match("B", "Non-P4 D1", "A", 85.0, 1),
        _make_school_match("C", "Non-P4 D1", "A-", 60.0, 3),
    ]

    _patch_preferences_router(monkeypatch, matches)

    client = TestClient(app)
    resp = client.post("/preferences/filter", json=_base_request("playing_time_score", "desc"))
    assert resp.status_code == 200
    schools = resp.json()["schools"]
    assert "recommendation_summary" in resp.json()
    assert [s["school_name"] for s in schools] == ["B", "A", "C"]
    assert all("scores" in s for s in schools)


def test_preferences_filter_sort_by_academic_grade(monkeypatch):
    matches = [
        _make_school_match("A", "Non-P4 D1", "B+", 70.0, 2),
        _make_school_match("B", "Non-P4 D1", "A", 85.0, 1),
        _make_school_match("C", "Non-P4 D1", "A-", 60.0, 3),
    ]

    _patch_preferences_router(monkeypatch, matches)

    client = TestClient(app)
    resp = client.post("/preferences/filter", json=_base_request("academic_grade", "desc"))
    assert resp.status_code == 200
    schools = resp.json()["schools"]
    assert [s["school_name"] for s in schools] == ["B", "C", "A"]


def test_preferences_filter_sort_by_nice_to_have(monkeypatch):
    matches = [
        _make_school_match("A", "Non-P4 D1", "B+", 70.0, 2),
        _make_school_match("B", "Non-P4 D1", "A", 85.0, 1),
        _make_school_match("C", "Non-P4 D1", "A-", 60.0, 3),
    ]

    _patch_preferences_router(monkeypatch, matches)

    client = TestClient(app)
    resp = client.post("/preferences/filter", json=_base_request("nice_to_have_count", "desc"))
    assert resp.status_code == 200
    schools = resp.json()["schools"]
    assert [s["school_name"] for s in schools] == ["C", "A", "B"]
