"""
Unit tests for backend.api.services.llm_insight_service.enqueue_deep_school_research.

Covers the decision tree that picks between "skipped" (OpenAI client missing,
Celery task missing, or empty school list), "processing" (Celery accepted the
job), and "failed" (Celery raised).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List

from backend.api.services import llm_insight_service
from backend.api.services.llm_insight_service import enqueue_deep_school_research


_SCHOOLS: List[Dict[str, Any]] = [
    {"school_name": "Alpha University", "delta": 0.5},
    {"school_name": "Beta College", "delta": 0.4},
]
_PLAYER_STATS: Dict[str, Any] = {"primary_position": "SS", "height": 72}
_BASEBALL_ASSESSMENT: Dict[str, Any] = {"predicted_tier": "Power 4"}
_ACADEMIC_SCORE: Dict[str, Any] = {"effective": 55.0}


def test_enqueue_returns_skipped_when_openai_client_unavailable(monkeypatch):
    monkeypatch.setattr(llm_insight_service, "_has_openai", False)
    monkeypatch.setattr(
        llm_insight_service,
        "generate_deep_school_research",
        SimpleNamespace(delay=lambda _payload: SimpleNamespace(id="unused")),
    )

    status, job_id = enqueue_deep_school_research(
        run_id="run-1",
        schools=[dict(s) for s in _SCHOOLS],
        player_stats=_PLAYER_STATS,
        baseball_assessment=_BASEBALL_ASSESSMENT,
        academic_score=_ACADEMIC_SCORE,
    )

    assert status == "skipped"
    assert job_id is None


def test_enqueue_returns_skipped_when_celery_task_unavailable(monkeypatch):
    monkeypatch.setattr(llm_insight_service, "_has_openai", True)
    monkeypatch.setattr(llm_insight_service, "generate_deep_school_research", None)

    status, job_id = enqueue_deep_school_research(
        run_id="run-1",
        schools=[dict(s) for s in _SCHOOLS],
        player_stats=_PLAYER_STATS,
        baseball_assessment=_BASEBALL_ASSESSMENT,
        academic_score=_ACADEMIC_SCORE,
    )

    assert status == "skipped"
    assert job_id is None


def test_enqueue_returns_skipped_when_schools_empty(monkeypatch):
    monkeypatch.setattr(llm_insight_service, "_has_openai", True)
    fake_task = SimpleNamespace(delay=lambda _payload: SimpleNamespace(id="should-not-fire"))
    monkeypatch.setattr(llm_insight_service, "generate_deep_school_research", fake_task)

    status, job_id = enqueue_deep_school_research(
        run_id="run-1",
        schools=[],
        player_stats=_PLAYER_STATS,
        baseball_assessment=_BASEBALL_ASSESSMENT,
        academic_score=_ACADEMIC_SCORE,
    )

    assert status == "skipped"
    assert job_id is None


def test_enqueue_returns_processing_and_job_id_on_success(monkeypatch):
    monkeypatch.setattr(llm_insight_service, "_has_openai", True)

    captured_payloads: List[Dict[str, Any]] = []

    def fake_delay(payload: Dict[str, Any]) -> SimpleNamespace:
        captured_payloads.append(payload)
        return SimpleNamespace(id="job-xyz")

    monkeypatch.setattr(
        llm_insight_service,
        "generate_deep_school_research",
        SimpleNamespace(delay=fake_delay),
    )
    # Roster URL lookup hits Supabase — neutralize it.
    monkeypatch.setattr(llm_insight_service, "attach_roster_urls", lambda _schools: None)

    status, job_id = enqueue_deep_school_research(
        run_id="run-42",
        schools=[dict(s) for s in _SCHOOLS],
        player_stats=_PLAYER_STATS,
        baseball_assessment=_BASEBALL_ASSESSMENT,
        academic_score=_ACADEMIC_SCORE,
        final_limit=15,
        ranking_priority="balanced",
    )

    assert status == "processing"
    assert job_id == "job-xyz"
    assert len(captured_payloads) == 1
    payload = captured_payloads[0]
    assert payload["run_id"] == "run-42"
    assert payload["final_limit"] == 15
    assert payload["ranking_priority"] == "balanced"
    assert len(payload["schools"]) == 2


def test_enqueue_returns_failed_when_celery_raises(monkeypatch):
    monkeypatch.setattr(llm_insight_service, "_has_openai", True)

    def fake_delay(_payload: Dict[str, Any]) -> None:
        raise RuntimeError("redis down")

    monkeypatch.setattr(
        llm_insight_service,
        "generate_deep_school_research",
        SimpleNamespace(delay=fake_delay),
    )
    monkeypatch.setattr(llm_insight_service, "attach_roster_urls", lambda _schools: None)

    status, job_id = enqueue_deep_school_research(
        run_id="run-1",
        schools=[dict(s) for s in _SCHOOLS],
        player_stats=_PLAYER_STATS,
        baseball_assessment=_BASEBALL_ASSESSMENT,
        academic_score=_ACADEMIC_SCORE,
    )

    assert status == "failed"
    assert job_id is None
