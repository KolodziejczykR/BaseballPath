"""Auth gating checks for protected routers."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routers.account import router as account_router
from backend.api.routers.evaluations import router as evaluations_router
from backend.api.routers.billing import router as billing_router


def test_account_me_requires_bearer_token():
    app = FastAPI()
    app.include_router(account_router, prefix="/account")
    client = TestClient(app)

    response = client.get("/account/me")
    assert response.status_code == 401


def test_evaluations_list_requires_bearer_token():
    app = FastAPI()
    app.include_router(evaluations_router, prefix="/evaluations")
    client = TestClient(app)

    response = client.get("/evaluations")
    assert response.status_code == 401


def test_evaluations_finalize_requires_bearer_token():
    app = FastAPI()
    app.include_router(evaluations_router, prefix="/evaluations")
    client = TestClient(app)

    response = client.post(
        "/evaluations/finalize",
        json={"session_token": "abc", "purchase_id": "xyz"},
    )
    assert response.status_code == 401


def test_billing_create_eval_checkout_requires_bearer_token():
    app = FastAPI()
    app.include_router(billing_router, prefix="/billing")
    client = TestClient(app)

    response = client.post(
        "/billing/create-eval-checkout",
        json={"session_token": "abc"},
    )
    assert response.status_code == 401
