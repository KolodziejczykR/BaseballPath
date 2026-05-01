"""
Integration tests for the /billing router.

Covers the happy paths for both endpoints. Stripe SDK calls are stubbed via
monkeypatch so no network is touched — `_require_stripe` is replaced with a
SimpleNamespace that mimics the two surfaces the router actually uses:
`checkout.Session.create(...)` and `Webhook.construct_event(...)`.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.deps.auth import AuthenticatedUser, get_current_user
from backend.api.routers import billing as billing_module
from backend.api.routers.billing import router as billing_router


def _auth_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="user-1",
        email="test@example.com",
        access_token="fake-token",
        claims={"sub": "user-1", "aud": "authenticated"},
    )


# ---------------------------------------------------------------------------
# Fake Supabase — tracks insert/update calls, returns canned data
# ---------------------------------------------------------------------------


class _FakeInsert:
    def __init__(
        self,
        parent: "_FakeSupabase",
        table_name: str,
        payload: Dict[str, Any],
    ):
        self._parent = parent
        self._table = table_name
        self._payload = payload

    def execute(self):
        # stripe_events models a unique (event_id) constraint — raise on
        # duplicate so the webhook idempotency guard can detect retries.
        if self._table == "stripe_events":
            event_id = self._payload.get("event_id")
            if event_id and event_id in self._parent.stripe_events_seen:
                raise RuntimeError(
                    f"duplicate key value violates unique constraint on event_id={event_id!r}"
                )
            if event_id:
                self._parent.stripe_events_seen.add(event_id)

        self._parent.inserts.append((self._table, self._payload))
        if self._table == "eval_purchases":
            row = {"id": "purchase-1", **self._payload}
            return SimpleNamespace(data=[row])
        return SimpleNamespace(data=[{"id": f"{self._table}-id"}])


class _FakeUpdate:
    def __init__(self, parent: "_FakeSupabase", table_name: str, payload: Dict[str, Any]):
        self._parent = parent
        self._table = table_name
        self._payload = payload
        self._filters: Dict[str, Any] = {}

    def eq(self, key: str, value: Any) -> "_FakeUpdate":
        self._filters[key] = value
        return self

    def execute(self):
        self._parent.updates.append(
            (self._table, dict(self._payload), dict(self._filters))
        )
        # Apply the update to the in-memory rows so subsequent selects see it.
        rows = self._parent.rows.get(self._table, [])
        for row in rows:
            if all(row.get(k) == v for k, v in self._filters.items()):
                row.update(self._payload)
        return SimpleNamespace(data=[])


class _FakeSelect:
    def __init__(self, parent: "_FakeSupabase", table_name: str):
        self._parent = parent
        self._table = table_name
        self._filters: Dict[str, Any] = {}
        self._limit: Optional[int] = None

    def eq(self, key: str, value: Any) -> "_FakeSelect":
        self._filters[key] = value
        return self

    def limit(self, n: int) -> "_FakeSelect":
        self._limit = n
        return self

    def execute(self):
        rows = self._parent.rows.get(self._table, [])
        matched = [
            row for row in rows
            if all(row.get(k) == v for k, v in self._filters.items())
        ]
        if self._limit is not None:
            matched = matched[: self._limit]
        return SimpleNamespace(data=list(matched))


class _FakeTable:
    def __init__(self, parent: "_FakeSupabase", name: str):
        self._parent = parent
        self._name = name

    def insert(self, payload: Dict[str, Any], **_kwargs: Any) -> _FakeInsert:
        # Accept (and ignore) Supabase kwargs like returning="minimal".
        return _FakeInsert(self._parent, self._name, payload)

    def update(self, payload: Dict[str, Any]) -> _FakeUpdate:
        return _FakeUpdate(self._parent, self._name, payload)

    def select(self, *_columns: str) -> _FakeSelect:
        return _FakeSelect(self._parent, self._name)


class _FakeSupabase:
    def __init__(self, rows: Optional[Dict[str, List[Dict[str, Any]]]] = None):
        self.inserts: List[tuple] = []
        self.updates: List[tuple] = []
        self.stripe_events_seen: set = set()
        # Pre-seeded rows visible to .select() calls; updates mutate these
        # in place so the webhook's "already completed?" check sees the
        # effect of a prior update if both happened in the same request.
        self.rows: Dict[str, List[Dict[str, Any]]] = rows or {}

    def table(self, name: str) -> _FakeTable:
        return _FakeTable(self, name)


# ---------------------------------------------------------------------------
# Fake Stripe — just enough surface for the router
# ---------------------------------------------------------------------------


def _fake_stripe_for_checkout() -> SimpleNamespace:
    created_sessions: List[Dict[str, Any]] = []

    def create_session(**kwargs: Any) -> SimpleNamespace:
        created_sessions.append(kwargs)
        return SimpleNamespace(id="cs_test_123", url="https://stripe.test/checkout")

    return SimpleNamespace(
        checkout=SimpleNamespace(Session=SimpleNamespace(create=create_session)),
        Webhook=SimpleNamespace(construct_event=lambda *_a, **_kw: {}),
        _created_sessions=created_sessions,
    )


def _fake_stripe_for_webhook(event_payload: Dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        checkout=SimpleNamespace(Session=SimpleNamespace(create=lambda **_kw: None)),
        Webhook=SimpleNamespace(construct_event=lambda *_a, **_kw: event_payload),
    )


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(billing_router, prefix="/billing")
    return app


# ---------------------------------------------------------------------------
# POST /billing/create-eval-checkout — happy path
# ---------------------------------------------------------------------------


def test_create_eval_checkout_happy_path(monkeypatch):
    supabase = _FakeSupabase()
    fake_stripe = _fake_stripe_for_checkout()

    monkeypatch.setattr(billing_module, "_require_stripe", lambda: fake_stripe)
    monkeypatch.setattr(
        billing_module, "require_supabase_admin_client", lambda: supabase
    )
    monkeypatch.setattr(
        billing_module,
        "get_eval_price",
        lambda user_id: {
            "price_cents": 6900,
            "is_first_eval": True,
            "completed_eval_count": 0,
        },
    )
    monkeypatch.setenv("APP_BASE_URL", "https://app.baseballpath.test")

    app = _make_app()
    app.dependency_overrides[get_current_user] = _auth_user
    client = TestClient(app)

    response = client.post(
        "/billing/create-eval-checkout",
        json={"session_token": "sess-xyz"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["checkout_url"] == "https://stripe.test/checkout"
    assert body["session_id"] == "cs_test_123"
    assert body["purchase_id"] == "purchase-1"

    # An eval_purchases row was inserted with user_id, pending status, first-eval price.
    purchase_inserts = [p for (table, p) in supabase.inserts if table == "eval_purchases"]
    assert len(purchase_inserts) == 1
    inserted = purchase_inserts[0]
    assert inserted["user_id"] == "user-1"
    assert inserted["status"] == "pending"
    assert inserted["amount_cents"] == 6900
    assert inserted["is_first_eval"] is True
    assert inserted["currency"] == "usd"

    # Stripe checkout session was created with the right metadata and URLs.
    assert len(fake_stripe._created_sessions) == 1
    created = fake_stripe._created_sessions[0]
    assert created["mode"] == "payment"
    assert created["customer_email"] == "test@example.com"
    assert created["client_reference_id"] == "user-1"
    assert created["line_items"][0]["price_data"]["unit_amount"] == 6900

    metadata = created["metadata"]
    assert metadata["purchase_id"] == "purchase-1"
    assert metadata["session_token"] == "sess-xyz"
    assert metadata["payment_type"] == "eval_purchase"
    assert metadata["user_id"] == "user-1"

    # Success URL should thread the purchase_id + session_token into the results URL.
    assert created["success_url"].startswith(
        "https://app.baseballpath.test/predict/results"
    )
    assert "purchase_id=purchase-1" in created["success_url"]
    assert "session_token=sess-xyz" in created["success_url"]

    # eval_purchases row was then updated with the Stripe session id.
    assert any(
        table == "eval_purchases"
        and payload.get("stripe_checkout_session_id") == "cs_test_123"
        for (table, payload, _filters) in supabase.updates
    )


def test_create_eval_checkout_uses_repeat_price_for_returning_users(monkeypatch):
    supabase = _FakeSupabase()
    fake_stripe = _fake_stripe_for_checkout()

    monkeypatch.setattr(billing_module, "_require_stripe", lambda: fake_stripe)
    monkeypatch.setattr(
        billing_module, "require_supabase_admin_client", lambda: supabase
    )
    monkeypatch.setattr(
        billing_module,
        "get_eval_price",
        lambda user_id: {
            "price_cents": 2900,
            "is_first_eval": False,
            "completed_eval_count": 2,
        },
    )

    app = _make_app()
    app.dependency_overrides[get_current_user] = _auth_user
    client = TestClient(app)

    response = client.post(
        "/billing/create-eval-checkout",
        json={"session_token": "sess-xyz"},
    )

    assert response.status_code == 200
    purchase_inserts = [p for (table, p) in supabase.inserts if table == "eval_purchases"]
    assert purchase_inserts[0]["amount_cents"] == 2900
    assert purchase_inserts[0]["is_first_eval"] is False
    # Line item label reflects repeat pricing.
    created = fake_stripe._created_sessions[0]
    assert created["line_items"][0]["price_data"]["product_data"]["name"] == (
        "BaseballPath Evaluation"
    )


# ---------------------------------------------------------------------------
# POST /billing/webhook
# ---------------------------------------------------------------------------


def _checkout_completed_event(event_id: str = "evt_test_001") -> Dict[str, Any]:
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_123",
                "payment_intent": "pi_test_789",
                "metadata": {
                    "payment_type": "eval_purchase",
                    "purchase_id": "purchase-1",
                    "session_token": "sess-xyz",
                    "user_id": "user-1",
                },
            }
        },
    }


def test_webhook_marks_eval_purchase_completed(monkeypatch):
    supabase = _FakeSupabase(
        rows={"eval_purchases": [{"id": "purchase-1", "status": "pending"}]}
    )
    fake_stripe = _fake_stripe_for_webhook(_checkout_completed_event())

    monkeypatch.setattr(billing_module, "_require_stripe", lambda: fake_stripe)
    monkeypatch.setattr(
        billing_module, "require_supabase_admin_client", lambda: supabase
    )
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")

    app = _make_app()
    client = TestClient(app)

    response = client.post(
        "/billing/webhook",
        content=b'{"stub": true}',
        headers={"stripe-signature": "t=0,v1=stub"},
    )

    assert response.status_code == 200
    assert response.json() == {"received": True}

    # eval_purchases row was updated to status=completed with the payment intent.
    completed_updates = [
        (payload, filters)
        for (table, payload, filters) in supabase.updates
        if table == "eval_purchases" and payload.get("status") == "completed"
    ]
    assert len(completed_updates) == 1
    payload, filters = completed_updates[0]
    assert payload["stripe_payment_intent_id"] == "pi_test_789"
    assert payload["stripe_checkout_session_id"] == "cs_test_123"
    assert filters == {"id": "purchase-1"}

    # The event id was claimed in stripe_events.
    assert any(
        table == "stripe_events" and p.get("event_id") == "evt_test_001"
        for (table, p) in supabase.inserts
    )


def test_webhook_ignores_non_eval_payment_types(monkeypatch):
    event = {
        "id": "evt_test_other",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_other",
                "metadata": {"payment_type": "not_eval_purchase"},
            }
        },
    }
    supabase = _FakeSupabase()
    fake_stripe = _fake_stripe_for_webhook(event)

    monkeypatch.setattr(billing_module, "_require_stripe", lambda: fake_stripe)
    monkeypatch.setattr(
        billing_module, "require_supabase_admin_client", lambda: supabase
    )
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")

    app = _make_app()
    client = TestClient(app)

    response = client.post(
        "/billing/webhook",
        content=b'{"stub": true}',
        headers={"stripe-signature": "t=0,v1=stub"},
    )

    assert response.status_code == 200
    assert response.json() == {"received": True, "ignored": True}
    # No eval_purchases updates should have been made.
    assert not any(table == "eval_purchases" for (table, _p, _f) in supabase.updates)


def test_webhook_dedupes_replayed_event_id(monkeypatch):
    """Stripe retries on transient failures. The same event_id must not
    re-process the purchase or fire side effects more than once."""
    supabase = _FakeSupabase(
        rows={"eval_purchases": [{"id": "purchase-1", "status": "pending"}]}
    )
    fake_stripe = _fake_stripe_for_webhook(_checkout_completed_event())

    monkeypatch.setattr(billing_module, "_require_stripe", lambda: fake_stripe)
    monkeypatch.setattr(
        billing_module, "require_supabase_admin_client", lambda: supabase
    )
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")

    app = _make_app()
    client = TestClient(app)

    # First delivery — should process normally.
    first = client.post(
        "/billing/webhook",
        content=b'{"stub": true}',
        headers={"stripe-signature": "t=0,v1=stub"},
    )
    assert first.status_code == 200
    assert first.json() == {"received": True}

    # Second delivery with the same event id — Stripe retry. Must skip.
    second = client.post(
        "/billing/webhook",
        content=b'{"stub": true}',
        headers={"stripe-signature": "t=0,v1=stub"},
    )
    assert second.status_code == 200
    assert second.json() == {"received": True, "duplicate": True}

    # Only ONE completed-status update should have been issued.
    completed_updates = [
        (table, p)
        for (table, p, _f) in supabase.updates
        if table == "eval_purchases" and p.get("status") == "completed"
    ]
    assert len(completed_updates) == 1


def test_webhook_skips_already_completed_purchase(monkeypatch):
    """Defense-in-depth: even if the event_id dedupe is bypassed (manual
    replay / restored backup / new event id for the same purchase), the
    purchase update must not re-fire on an already-completed row."""
    supabase = _FakeSupabase(
        rows={"eval_purchases": [{"id": "purchase-1", "status": "completed"}]}
    )
    fake_stripe = _fake_stripe_for_webhook(
        _checkout_completed_event(event_id="evt_brand_new_id")
    )

    monkeypatch.setattr(billing_module, "_require_stripe", lambda: fake_stripe)
    monkeypatch.setattr(
        billing_module, "require_supabase_admin_client", lambda: supabase
    )
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")

    app = _make_app()
    client = TestClient(app)

    response = client.post(
        "/billing/webhook",
        content=b'{"stub": true}',
        headers={"stripe-signature": "t=0,v1=stub"},
    )
    assert response.status_code == 200
    assert response.json() == {"received": True, "duplicate_completion": True}

    # No new completed-status updates should have been issued.
    assert not any(
        table == "eval_purchases" and p.get("status") == "completed"
        for (table, p, _f) in supabase.updates
    )


def test_webhook_rejects_missing_signature(monkeypatch):
    monkeypatch.setattr(
        billing_module,
        "_require_stripe",
        lambda: _fake_stripe_for_webhook({"type": "noop"}),
    )
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")

    app = _make_app()
    client = TestClient(app)

    response = client.post("/billing/webhook", content=b'{"stub": true}')
    assert response.status_code == 400
    assert "Missing Stripe signature" in response.json()["detail"]


def test_webhook_rejects_invalid_signature(monkeypatch):
    def raising_construct_event(*_args, **_kwargs):
        raise ValueError("invalid signature")

    fake_stripe = SimpleNamespace(
        checkout=SimpleNamespace(Session=SimpleNamespace(create=lambda **_kw: None)),
        Webhook=SimpleNamespace(construct_event=raising_construct_event),
    )
    monkeypatch.setattr(billing_module, "_require_stripe", lambda: fake_stripe)
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")

    app = _make_app()
    client = TestClient(app)

    response = client.post(
        "/billing/webhook",
        content=b'{"stub": true}',
        headers={"stripe-signature": "t=0,v1=bad"},
    )
    assert response.status_code == 400
    assert "Invalid webhook signature" in response.json()["detail"]
