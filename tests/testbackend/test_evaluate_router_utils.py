from types import SimpleNamespace

import pytest

from backend.api.services.evaluation_service import (
    LegacyPositionTrackConstraintError,
    _insert_prediction_run,
    _is_prediction_runs_position_track_constraint_error,
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
            raise Exception(
                '{"message":"violates check constraint prediction_runs_position_track_check"}'
            )
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


def test_insert_raises_legacy_constraint_error_for_catcher():
    supabase = _FakeSupabase(fail_first_catcher_insert=True)
    payload = {"position_track": "catcher", "stats_input": {}}

    with pytest.raises(LegacyPositionTrackConstraintError) as exc:
        _insert_prediction_run(supabase, payload)

    assert "20260327_prediction_runs_add_catcher.sql" in str(exc.value)
    assert len(supabase.calls) == 1
    assert supabase.calls[0]["position_track"] == "catcher"


def test_insert_succeeds_without_retry_when_constraint_is_not_hit():
    supabase = _FakeSupabase(fail_first_catcher_insert=False)
    payload = {"position_track": "outfielder", "stats_input": {}}

    response = _insert_prediction_run(supabase, payload)

    assert response.data == [{"id": "run-1"}]
    assert len(supabase.calls) == 1
    assert supabase.calls[0]["position_track"] == "outfielder"
