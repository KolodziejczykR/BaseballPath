from datetime import date

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.api.routers.account import router as account_router
from backend.api.services.plan_service import (
    EffectivePlan,
    UsageSnapshot,
    enforce_evaluation_quota,
    remaining_evaluations,
)


def test_account_endpoint_requires_bearer_token():
    app = FastAPI()
    app.include_router(account_router, prefix="/account")
    client = TestClient(app)

    response = client.get("/account/me")
    assert response.status_code == 401


def test_remaining_evaluations_for_limited_plan():
    effective_plan = EffectivePlan(
        plan_tier="starter",
        status="none",
        subscription=None,
        monthly_eval_limit=5,
        llm_enabled=False,
    )
    usage = UsageSnapshot(period_start=date(2026, 2, 1), eval_count=3, llm_count=0)
    assert remaining_evaluations(effective_plan, usage) == 2


def test_enforce_evaluation_quota_blocks_over_limit(monkeypatch):
    def fake_usage(_user_id: str, _period_start=None):
        return UsageSnapshot(period_start=date(2026, 2, 1), eval_count=5, llm_count=0)

    monkeypatch.setattr("backend.api.services.plan_service.get_monthly_usage", fake_usage)

    effective_plan = EffectivePlan(
        plan_tier="starter",
        status="none",
        subscription=None,
        monthly_eval_limit=5,
        llm_enabled=False,
    )

    with pytest.raises(HTTPException) as exc:
        enforce_evaluation_quota("user-123", effective_plan)

    assert exc.value.status_code == 429
