"""
Pure unit tests for backend.api.services.evaluation_service.

These tests avoid hitting Supabase or the real matching pipeline. They cover:
  * build_teaser — deterministic with a seeded RNG, strips to teaser fields
  * CoreEvaluation.baseball_assessment — shape of the summary dict
  * exception hierarchy — PurchaseNotFound / PendingEvaluationNotFound types
  * run_preview_core — deterministic with mocked DB + matching
  * finalize_paid_evaluation — happy path, missing purchase, missing pending
"""

from __future__ import annotations

import random
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest

from backend.api.services import evaluation_service
from backend.api.services.evaluation_service import (
    AcademicInput,
    BaseballMetrics,
    CoreEvaluation,
    MLPrediction,
    PendingEvaluationNotFound,
    PreferencesInput,
    PurchaseNotFound,
    TEASER_COUNT,
    TEASER_POOL_SIZE,
    build_teaser,
    finalize_paid_evaluation,
    run_preview_core,
)


def _fake_school(idx: int) -> Dict[str, Any]:
    return {
        "school_name": f"School {idx}",
        "display_school_name": f"School {idx} University",
        "division_group": "Power 4" if idx < 3 else "Non-P4",
        "division_label": "Power 4" if idx < 3 else "Division 1",
        "baseball_division": 1,
        "school_logo_image": f"school-{idx}",
        "extra_noise_field": "should_be_stripped",
    }


def _core_with_schools(n: int) -> CoreEvaluation:
    schools: List[Dict[str, Any]] = [_fake_school(i) for i in range(n)]
    return CoreEvaluation(
        academic_score={"effective": 50.0},
        player_stats={},
        predicted_tier="Power 4",
        player_percentile=72.0,
        player_pci=68.0,
        ml_pci=64.0,
        is_pitcher=False,
        ranked_schools=schools,
    )


# ---------------------------------------------------------------------------
# build_teaser
# ---------------------------------------------------------------------------


def test_build_teaser_picks_three_from_top_pool_size():
    core = _core_with_schools(20)
    rng = random.Random(42)

    teasers = build_teaser(core, rng=rng)

    assert len(teasers) == TEASER_COUNT
    # All picks must come from the top TEASER_POOL_SIZE (indexes 0..9)
    names = [t["school_name"] for t in teasers]
    pool_names = [f"School {i}" for i in range(TEASER_POOL_SIZE)]
    for name in names:
        assert name in pool_names


def test_build_teaser_strips_to_teaser_fields_only():
    core = _core_with_schools(15)
    rng = random.Random(0)

    teasers = build_teaser(core, rng=rng)

    allowed = {
        "school_name",
        "display_school_name",
        "division_group",
        "division_label",
        "baseball_division",
        "school_logo_image",
    }
    for t in teasers:
        assert set(t.keys()) == allowed
        assert "extra_noise_field" not in t


def test_build_teaser_deterministic_with_seeded_rng():
    core = _core_with_schools(15)

    rng_a = random.Random(123)
    rng_b = random.Random(123)

    teasers_a = build_teaser(core, rng=rng_a)
    teasers_b = build_teaser(core, rng=rng_b)

    assert teasers_a == teasers_b


def test_build_teaser_handles_short_pool():
    core = _core_with_schools(2)  # fewer than TEASER_COUNT

    teasers = build_teaser(core, rng=random.Random(7))

    assert len(teasers) == 2


def test_build_teaser_returns_empty_when_no_schools():
    core = _core_with_schools(0)

    assert build_teaser(core) == []


# ---------------------------------------------------------------------------
# CoreEvaluation.baseball_assessment
# ---------------------------------------------------------------------------


def test_baseball_assessment_shape():
    core = _core_with_schools(1)
    ml = MLPrediction(
        final_prediction="Power 4",
        d1_probability=0.81,
        p4_probability=0.45,
        confidence="high",
    )

    result = core.baseball_assessment(ml)

    assert result == {
        "predicted_tier": "Power 4",
        "within_tier_percentile": 72.0,
        "player_competitiveness_index": 68.0,
        "ml_pci": 64.0,
        "d1_probability": 0.81,
        "p4_probability": 0.45,
    }


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


def test_exception_types_are_lookup_errors():
    # PurchaseNotFound and PendingEvaluationNotFound must be LookupError
    # subclasses so callers can `except LookupError` if they prefer.
    assert issubclass(PurchaseNotFound, LookupError)
    assert issubclass(PendingEvaluationNotFound, LookupError)


# ---------------------------------------------------------------------------
# run_preview_core — determinism with mocked DB + ranking
# ---------------------------------------------------------------------------


def _baseball_metrics() -> BaseballMetrics:
    return BaseballMetrics(
        height=72,
        weight=185,
        primary_position="SS",
        throwing_hand="R",
        graduation_year=2027,
        exit_velo_max=94.0,
        sixty_time=6.7,
        inf_velo=82.0,
    )


def _academic_input() -> AcademicInput:
    return AcademicInput(gpa=3.6, sat_score=1320, act_score=None, ap_courses=4)


def _preferences() -> PreferencesInput:
    return PreferencesInput(regions=["Northeast"], max_budget="no_preference")


def _ml_prediction() -> MLPrediction:
    return MLPrediction(
        final_prediction="Power 4",
        d1_probability=0.81,
        p4_probability=0.45,
        confidence="high",
    )


class _FakeAsyncDB:
    instances: List["_FakeAsyncDB"] = []

    def __init__(self):
        self.closed = False
        _FakeAsyncDB.instances.append(self)

    async def get_all_schools(self):
        return [{"school_name": f"Seed{i}", "some_field": i} for i in range(20)]

    async def close(self):
        self.closed = True


async def test_run_preview_core_is_deterministic_with_mocked_db(monkeypatch):
    _FakeAsyncDB.instances = []
    monkeypatch.setattr(evaluation_service, "AsyncSchoolDataQueries", _FakeAsyncDB)
    canned_schools = [_fake_school(i) for i in range(12)]
    monkeypatch.setattr(
        evaluation_service,
        "match_and_rank_schools",
        lambda **_kwargs: [dict(s) for s in canned_schools],
    )

    core_a = await run_preview_core(
        _baseball_metrics(), _ml_prediction(), _academic_input(), _preferences()
    )
    core_b = await run_preview_core(
        _baseball_metrics(), _ml_prediction(), _academic_input(), _preferences()
    )

    # @dataclass provides structural equality, so same inputs → equal cores.
    assert core_a == core_b
    # And the DB client was closed on both calls.
    assert len(_FakeAsyncDB.instances) == 2
    assert all(instance.closed for instance in _FakeAsyncDB.instances)


# ---------------------------------------------------------------------------
# finalize_paid_evaluation — happy path + error branches
# ---------------------------------------------------------------------------


class _FakeQuery:
    def __init__(self, data: List[Dict[str, Any]]):
        self._data = data

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        return SimpleNamespace(data=list(self._data))


class _FakeInsert:
    def __init__(self, parent: "_FakeSupabase", table_name: str, payload: Dict[str, Any]):
        self._parent = parent
        self._table = table_name
        self._payload = payload

    def execute(self):
        self._parent.inserts.append((self._table, self._payload))
        if self._table == "prediction_runs":
            return SimpleNamespace(data=[{"id": "run-123"}])
        return SimpleNamespace(data=[{"id": f"{self._table}-id"}])


class _FakeUpdate:
    def __init__(self, parent: "_FakeSupabase", table_name: str, payload: Dict[str, Any]):
        self._parent = parent
        self._table = table_name
        self._payload = payload

    def eq(self, *_args, **_kwargs):
        return self

    def execute(self):
        self._parent.updates.append((self._table, dict(self._payload)))
        return SimpleNamespace(data=[])


class _FakeTable:
    def __init__(self, parent: "_FakeSupabase", name: str):
        self._parent = parent
        self._name = name

    def select(self, *_args, **_kwargs):
        return _FakeQuery(self._parent.data.get(self._name, []))

    def insert(self, payload: Dict[str, Any]) -> _FakeInsert:
        return _FakeInsert(self._parent, self._name, payload)

    def update(self, payload: Dict[str, Any]) -> _FakeUpdate:
        return _FakeUpdate(self._parent, self._name, payload)

    def delete(self):  # pragma: no cover - unused but kept for symmetry
        return self


class _FakeSupabase:
    def __init__(self, data: Optional[Dict[str, List[Dict[str, Any]]]] = None):
        self.data = data or {}
        self.inserts: List[tuple] = []
        self.updates: List[tuple] = []

    def table(self, name: str) -> _FakeTable:
        return _FakeTable(self, name)


def _pending_row() -> Dict[str, Any]:
    return {
        "session_token": "sess-1",
        "baseball_metrics": {
            "height": 72,
            "weight": 185,
            "primary_position": "SS",
            "throwing_hand": "R",
            "graduation_year": 2027,
        },
        "ml_prediction": {
            "final_prediction": "Power 4",
            "d1_probability": 0.81,
            "p4_probability": 0.45,
            "confidence": "high",
        },
        "academic_input": {
            "gpa": 3.6,
            "sat_score": 1320,
            "act_score": None,
            "ap_courses": 4,
        },
        "preferences": {
            "regions": ["Northeast"],
            "max_budget": "no_preference",
            "ranking_priority": "balanced",
        },
        "preview_results": {
            "schools": [_fake_school(i) for i in range(5)],
            "academic_score": {"effective": 50.0},
            "baseball_assessment": {
                "predicted_tier": "Power 4",
                "within_tier_percentile": 72.0,
                "player_competitiveness_index": 68.0,
                "ml_pci": 64.0,
                "d1_probability": 0.81,
                "p4_probability": 0.45,
            },
        },
    }


def _purchase_row(user_id: str = "user-1") -> Dict[str, Any]:
    return {"id": "purchase-1", "user_id": user_id, "status": "pending"}


async def _fake_run_preview_core(*_args, **_kwargs) -> CoreEvaluation:
    return _core_with_schools(5)


async def test_finalize_happy_path_persists_run_with_user_id(monkeypatch):
    supabase = _FakeSupabase(
        data={
            "eval_purchases": [_purchase_row()],
            "pending_evaluations": [_pending_row()],
        }
    )
    monkeypatch.setattr(
        evaluation_service, "require_supabase_admin_client", lambda: supabase
    )
    monkeypatch.setattr(
        evaluation_service,
        "get_profile",
        lambda user_id, email=None: {"full_name": "Test Player", "state": "CA"},
    )
    monkeypatch.setattr(evaluation_service, "run_preview_core", _fake_run_preview_core)
    monkeypatch.setattr(
        evaluation_service,
        "should_enqueue_deep_school_research",
        lambda schools: True,
    )
    monkeypatch.setattr(
        evaluation_service,
        "enqueue_deep_school_research",
        lambda **_kwargs: ("processing", "job-abc"),
    )

    result = await finalize_paid_evaluation(
        user_id="user-1",
        user_email="test@example.com",
        session_token="sess-1",
        purchase_id="purchase-1",
    )

    assert result["run_id"] == "run-123"
    assert result["llm_reasoning_status"] == "processing"
    assert result["baseball_assessment"]["predicted_tier"] == "Power 4"

    # A prediction_runs insert happened with user_id bound to the caller.
    prediction_inserts = [
        p for (table, p) in supabase.inserts if table == "prediction_runs"
    ]
    assert len(prediction_inserts) == 1
    inserted = prediction_inserts[0]
    assert inserted["user_id"] == "user-1"
    assert inserted["purchase_id"] == "purchase-1"

    # eval_purchases was linked to the new run, and prediction_runs was updated
    # with the Celery job id.
    assert any(table == "eval_purchases" for (table, _) in supabase.updates)
    assert any(
        table == "prediction_runs" and payload.get("llm_job_id") == "job-abc"
        for (table, payload) in supabase.updates
    )


async def test_finalize_raises_purchase_not_found_when_missing(monkeypatch):
    supabase = _FakeSupabase(
        data={"eval_purchases": [], "pending_evaluations": []}
    )
    monkeypatch.setattr(
        evaluation_service, "require_supabase_admin_client", lambda: supabase
    )

    with pytest.raises(PurchaseNotFound):
        await finalize_paid_evaluation(
            user_id="user-1",
            user_email="test@example.com",
            session_token="sess-1",
            purchase_id="missing",
        )


async def test_finalize_raises_purchase_not_found_for_different_user(monkeypatch):
    supabase = _FakeSupabase(
        data={
            "eval_purchases": [_purchase_row(user_id="someone-else")],
            "pending_evaluations": [_pending_row()],
        }
    )
    monkeypatch.setattr(
        evaluation_service, "require_supabase_admin_client", lambda: supabase
    )

    with pytest.raises(PurchaseNotFound):
        await finalize_paid_evaluation(
            user_id="user-1",
            user_email="test@example.com",
            session_token="sess-1",
            purchase_id="purchase-1",
        )


async def test_finalize_raises_pending_not_found_when_session_expired(monkeypatch):
    supabase = _FakeSupabase(
        data={
            "eval_purchases": [_purchase_row()],
            "pending_evaluations": [],
        }
    )
    monkeypatch.setattr(
        evaluation_service, "require_supabase_admin_client", lambda: supabase
    )

    with pytest.raises(PendingEvaluationNotFound):
        await finalize_paid_evaluation(
            user_id="user-1",
            user_email="test@example.com",
            session_token="sess-expired",
            purchase_id="purchase-1",
        )
