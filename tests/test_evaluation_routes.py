"""
Integration tests for the /evaluations router.

Covers the happy paths and error translations that the service-level tests
can't express without FastAPI's dependency overrides.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from backend.api.deps.auth import (
    AuthenticatedUser,
    get_current_user,
    get_optional_user,
)
from backend.api.rate_limit import limiter
from backend.api.routers.evaluations import router as evaluations_router
from backend.api.services import evaluation_service
from backend.api.services.evaluation_service import (
    CoreEvaluation,
    PendingEvaluationNotFound,
    PurchaseNotFound,
)


def _auth_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="user-1",
        email="test@example.com",
        access_token="fake-token",
        claims={"sub": "user-1", "aud": "authenticated"},
    )


def _fake_ranked_schools(n: int = 10) -> List[Dict[str, Any]]:
    return [
        {
            "school_name": f"School {i}",
            "display_school_name": f"School {i} University",
            "division_group": "Power 4",
            "division_label": "Power 4",
            "baseball_division": 1,
            "school_logo_image": f"school-{i}",
        }
        for i in range(n)
    ]


def _fake_core(n: int = 10) -> CoreEvaluation:
    return CoreEvaluation(
        academic_score={"effective": 55.0},
        player_stats={"primary_position": "SS"},
        predicted_tier="Power 4",
        player_percentile=72.0,
        player_pci=68.0,
        ml_pci=64.0,
        is_pitcher=False,
        ranked_schools=_fake_ranked_schools(n),
    )


def _eval_payload() -> Dict[str, Any]:
    return {
        "baseball_metrics": {
            "height": 72,
            "weight": 185,
            "primary_position": "SS",
            "throwing_hand": "R",
            "graduation_year": 2027,
            "exit_velo_max": 94.0,
            "sixty_time": 6.7,
            "inf_velo": 82.0,
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
    }


def _make_app() -> FastAPI:
    """Build a test app that mirrors production wiring.

    The shared SlowAPI limiter must be attached to ``app.state.limiter``
    AND the RateLimitExceeded handler must be registered, otherwise the
    decorated routes (e.g. /evaluations/preview) lose their body
    annotations during FastAPI introspection and 422 with
    "payload missing from query".
    """
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(evaluations_router, prefix="/evaluations")
    return app


# ---------------------------------------------------------------------------
# POST /evaluations/preview
# ---------------------------------------------------------------------------


def test_preview_anonymous_returns_teaser_and_stores_pending(monkeypatch):
    store_calls: List[Dict[str, Any]] = []

    async def fake_run_preview_core(*_args, **_kwargs) -> CoreEvaluation:
        return _fake_core(10)

    def fake_store(*, session_token, payload, core, user_id):
        store_calls.append(
            {
                "session_token": session_token,
                "user_id": user_id,
                "core_size": len(core.ranked_schools),
            }
        )

    monkeypatch.setattr(evaluation_service, "run_preview_core", fake_run_preview_core)
    monkeypatch.setattr(evaluation_service, "store_pending_evaluation", fake_store)

    app = _make_app()
    app.dependency_overrides[get_optional_user] = lambda: None
    client = TestClient(app)

    response = client.post("/evaluations/preview", json=_eval_payload())

    assert response.status_code == 200
    body = response.json()
    assert "session_token" in body and body["session_token"]
    assert len(body["teaser_schools"]) == 3
    for teaser in body["teaser_schools"]:
        assert set(teaser.keys()) == {
            "school_name",
            "display_school_name",
            "division_group",
            "division_label",
            "baseball_division",
            "school_logo_image",
        }
    # Anonymous caller → no pricing info is attached.
    assert body["price_cents"] is None
    assert body["is_first_eval"] is None

    # Pending evaluation was stored with matching session token and no user_id.
    assert len(store_calls) == 1
    assert store_calls[0]["session_token"] == body["session_token"]
    assert store_calls[0]["user_id"] is None
    assert store_calls[0]["core_size"] == 10


# ---------------------------------------------------------------------------
# POST /evaluations/finalize
# ---------------------------------------------------------------------------


def test_finalize_returns_404_when_purchase_missing(monkeypatch):
    async def fake_finalize(**_kwargs):
        raise PurchaseNotFound("Purchase not found")

    monkeypatch.setattr(evaluation_service, "finalize_paid_evaluation", fake_finalize)

    app = _make_app()
    app.dependency_overrides[get_current_user] = _auth_user
    client = TestClient(app)

    response = client.post(
        "/evaluations/finalize",
        json={"session_token": "sess-1", "purchase_id": "missing"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Purchase not found"


def test_finalize_returns_404_when_pending_missing(monkeypatch):
    async def fake_finalize(**_kwargs):
        raise PendingEvaluationNotFound("Pending evaluation not found or expired")

    monkeypatch.setattr(evaluation_service, "finalize_paid_evaluation", fake_finalize)

    app = _make_app()
    app.dependency_overrides[get_current_user] = _auth_user
    client = TestClient(app)

    response = client.post(
        "/evaluations/finalize",
        json={"session_token": "sess-stale", "purchase_id": "purchase-1"},
    )
    assert response.status_code == 404


def test_finalize_happy_path_returns_run_id(monkeypatch):
    async def fake_finalize(**_kwargs) -> Dict[str, Any]:
        return {
            "run_id": "run-123",
            "disclaimer": "stub",
            "baseball_assessment": {"predicted_tier": "Power 4"},
            "academic_assessment": {"effective": 55.0},
            "schools": [],
            "llm_reasoning_status": "processing",
        }

    monkeypatch.setattr(evaluation_service, "finalize_paid_evaluation", fake_finalize)

    app = _make_app()
    app.dependency_overrides[get_current_user] = _auth_user
    client = TestClient(app)

    response = client.post(
        "/evaluations/finalize",
        json={"session_token": "sess-1", "purchase_id": "purchase-1"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == "run-123"
    assert body["llm_reasoning_status"] == "processing"
    assert body["baseball_assessment"]["predicted_tier"] == "Power 4"
