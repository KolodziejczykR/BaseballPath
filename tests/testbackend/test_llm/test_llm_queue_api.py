from types import SimpleNamespace
import importlib

from fastapi.testclient import TestClient

from backend.api.main import app
from backend.utils.school_match_types import SchoolMatch, NiceToHaveMatch, NiceToHaveType
from backend.utils.recommendation_types import PlayingTimeInfo


def _make_school_match(name):
    school_data = {
        "school_name": name,
        "school_state": "CA",
        "school_region": "West",
        "undergrad_enrollment": 8000,
        "academics_grade": "B+",
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
            preference_name="preferred_states",
            user_value=["CA"],
            school_value="CA",
            description="School is in preferred state",
        )
    ]
    return SchoolMatch(
        school_name=name,
        school_data=school_data,
        division_group="Non-P4 D1",
        nice_to_have_matches=matches,
        nice_to_have_misses=[],
        playing_time_result=SimpleNamespace(percentile=75.0),
    )


def _mock_filtering_result(school_matches):
    return SimpleNamespace(
        school_matches=school_matches,
        must_have_count=len(school_matches),
        total_schools_considered=len(school_matches),
    )


def _base_request(use_llm_reasoning=True):
    return {
        "user_preferences": {
            "user_state": "CA",
            "preferred_states": ["CA"],
            "must_have_preferences": ["preferred_states"]
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
        "use_llm_reasoning": use_llm_reasoning,
    }


def test_preferences_filter_queues_llm_job(monkeypatch):
    pref_mod = importlib.import_module("api.preferences_router")

    async def _mock_get_school_matches_shared(preferences, ml_results, limit):
        return _mock_filtering_result([_make_school_match("Alpha College")])

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

    captured = {}

    class _FakeTask:
        def delay(self, payload):
            captured["payload"] = payload
            return SimpleNamespace(id="job123")

    monkeypatch.setattr(pref_mod, "generate_llm_reasoning", _FakeTask())

    client = TestClient(app)
    resp = client.post("/preferences/filter", json=_base_request(True))
    assert resp.status_code == 200
    data = resp.json()
    assert data["recommendation_summary"]["llm_job_id"] == "job123"
    assert data["recommendation_summary"]["llm_status"] == "queued"
    assert "schools" in captured["payload"]
    assert captured["payload"]["schools"][0]["school_name"] == "Alpha College"


def test_reasoning_endpoint_pending(monkeypatch):
    pref_mod = importlib.import_module("api.preferences_router")

    class _FakeAsyncResult:
        status = "PENDING"

        def ready(self):
            return False

        def failed(self):
            return False

    monkeypatch.setattr(pref_mod, "AsyncResult", lambda _: _FakeAsyncResult())

    client = TestClient(app)
    resp = client.get("/preferences/reasoning/job123")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert data["reasoning"] is None


def test_reasoning_endpoint_completed(monkeypatch):
    pref_mod = importlib.import_module("api.preferences_router")

    class _FakeAsyncResult:
        status = "SUCCESS"
        result = {
            "reasoning": {"Alpha College": {"summary": "Fit", "fit_qualities": [], "cautions": []}},
            "player_summary": "Summary",
            "relax_suggestions": [],
            "completed_at": "2026-02-06T00:00:00"
        }

        def ready(self):
            return True

        def failed(self):
            return False

    monkeypatch.setattr(pref_mod, "AsyncResult", lambda _: _FakeAsyncResult())

    client = TestClient(app)
    resp = client.get("/preferences/reasoning/job123")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert "Alpha College" in data["reasoning"]
    assert data["player_summary"] == "Summary"


def test_reasoning_endpoint_failed(monkeypatch):
    pref_mod = importlib.import_module("api.preferences_router")

    class _FakeAsyncResult:
        status = "FAILURE"

        def ready(self):
            return True

        def failed(self):
            return True

    monkeypatch.setattr(pref_mod, "AsyncResult", lambda _: _FakeAsyncResult())

    client = TestClient(app)
    resp = client.get("/preferences/reasoning/job123")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "failed"


def test_reasoning_endpoint_job_not_found(monkeypatch):
    pref_mod = importlib.import_module("api.preferences_router")
    monkeypatch.setattr(pref_mod, "AsyncResult", lambda _: None)

    client = TestClient(app)
    resp = client.get("/preferences/reasoning/job123")
    assert resp.status_code == 404


def test_preferences_filter_no_llm_job_when_disabled(monkeypatch):
    pref_mod = importlib.import_module("api.preferences_router")

    async def _mock_get_school_matches_shared(preferences, ml_results, limit):
        return _mock_filtering_result([_make_school_match("Alpha College")])

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

    class _FakeTask:
        def delay(self, payload):
            raise AssertionError("LLM task should not be queued when disabled")

    monkeypatch.setattr(pref_mod, "generate_llm_reasoning", _FakeTask())

    client = TestClient(app)
    resp = client.post("/preferences/filter", json=_base_request(False))
    assert resp.status_code == 200
    data = resp.json()
    assert data["recommendation_summary"]["llm_job_id"] is None
    assert data["recommendation_summary"]["llm_status"] is None
