from types import SimpleNamespace

from fastapi import HTTPException

from backend.api.routers.evaluate import (
    _insert_prediction_run,
    _is_prediction_runs_position_track_constraint_error,
    _position_endpoint,
)


class _FakeInsert:
    def __init__(self, supabase, payload):
        self._supabase = supabase
        self._payload = payload

    def execute(self):
        self._supabase.calls.append(self._payload)
        if (
            self._supabase.fail_first_catcher_insert
            and self._payload.get("position_track") == "catcher"
        ):
            raise Exception('{"message":"violates check constraint prediction_runs_position_track_check"}')
        return SimpleNamespace(data=[{"id": "run-1"}])


class _FakeTable:
    def __init__(self, supabase):
        self._supabase = supabase

    def insert(self, payload):
        return _FakeInsert(self._supabase, payload)


class _FakeSupabase:
    def __init__(self, fail_first_catcher_insert=True):
        self.fail_first_catcher_insert = fail_first_catcher_insert
        self.calls = []

    def table(self, name):
        assert name == "prediction_runs"
        return _FakeTable(self)


def test_detects_position_track_constraint_error():
    exc = Exception("prediction_runs_position_track_check")
    assert _is_prediction_runs_position_track_constraint_error(exc) is True
    assert _is_prediction_runs_position_track_constraint_error(Exception("different error")) is False


def test_insert_raises_clean_http_error_for_legacy_position_track_constraint():
    supabase = _FakeSupabase(fail_first_catcher_insert=True)
    payload = {"position_track": "catcher", "stats_input": {}}

    try:
        _insert_prediction_run(supabase, payload)
        assert False, "Expected HTTPException for legacy schema mismatch"
    except HTTPException as exc:
        assert exc.status_code == 500
        assert "20260327_prediction_runs_add_catcher.sql" in str(exc.detail)
    assert len(supabase.calls) == 1
    assert supabase.calls[0]["position_track"] == "catcher"


def test_insert_succeeds_without_retry_when_constraint_is_not_hit():
    supabase = _FakeSupabase(fail_first_catcher_insert=False)
    payload = {"position_track": "outfielder", "stats_input": {}}

    response = _insert_prediction_run(supabase, payload)

    assert response.data == [{"id": "run-1"}]
    assert len(supabase.calls) == 1
    assert supabase.calls[0]["position_track"] == "outfielder"


def test_position_endpoint_handles_catcher_aliases_and_known_tracks():
    assert _position_endpoint("C") == "catcher"
    assert _position_endpoint("catcher") == "catcher"
    assert _position_endpoint("OF") == "outfielder"
    assert _position_endpoint("rhp") == "pitcher"
    assert _position_endpoint("SS") == "infielder"
