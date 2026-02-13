# Backend API Guide

This folder now contains production auth, billing, and persisted evaluation orchestration.

## Directory Layout

- `routers/`: FastAPI route handlers grouped by domain.
- `deps/`: shared FastAPI dependencies (auth).
- `services/`: business logic helpers (plan/usage/entitlements).
- `clients/`: external client setup helpers (Supabase admin client).
- `main.py`: primary FastAPI app entrypoint.
- `main_waitlist.py`: waitlist-only app entrypoint.

## What Was Implemented

### Auth + Account

- Protected token verification dependency:
  - `deps/auth.py`
- Account endpoints:
  - `GET /account/me`
  - `PATCH /account/me`
  - Router: `routers/account.py`

### Evaluations Persistence

- Orchestrated evaluation endpoint:
  - `POST /evaluations/run`
- Evaluation history endpoints:
  - `GET /evaluations`
  - `GET /evaluations/{run_id}`
- Router: `routers/evaluations.py`

`POST /evaluations/run` does:
1. Authenticate user.
2. Ensure profile exists.
3. Enforce plan quota.
4. Run ML prediction pipeline.
5. Run school filtering pipeline.
6. Persist run to `prediction_runs`.
7. Increment monthly usage.
8. Return run id + prediction + preference results + entitlement metadata.

### Billing

- Billing endpoints:
  - `POST /billing/create-checkout-session`
  - `POST /billing/create-portal-session`
  - `POST /billing/webhook`
- Router: `routers/billing.py`
- Stripe webhook syncs `subscriptions` table.

### Plan Entitlements

- Service: `services/plan_service.py`
- Current defaults:
  - `starter`: 5 evaluations/month, no LLM reasoning
  - `pro`: 50 evaluations/month, no LLM reasoning
  - `elite`: unlimited evaluations, LLM reasoning enabled

For detailed billing/plan configuration changes, read:
- `services/PAYMENT_PLANS.md`

## How It Works End-to-End

1. Frontend user signs in via Supabase Auth.
2. Frontend calls protected endpoints with `Authorization: Bearer <token>`.
3. API validates token and identifies `user_id`.
4. API derives effective plan from `subscriptions` (fallback `starter`).
5. API enforces monthly quotas from `plan_usage_monthly`.
6. API persists all evaluation data in `prediction_runs`.
7. Stripe webhook updates plan tier/status in `subscriptions`.

## Local Setup Checklist

1. Run migration SQL:
   - `backend/database/migrations/20260211_auth_and_entitlements.sql`
2. Set backend env vars:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`
   - `SUPABASE_ANON_KEY`
   - `SUPABASE_JWT_ISSUER` (optional)
   - `SUPABASE_JWT_AUDIENCE` (optional)
   - `STRIPE_SECRET_KEY`
   - `STRIPE_WEBHOOK_SECRET`
   - `STRIPE_PRICE_ID_PRO`
   - `STRIPE_PRICE_ID_ELITE`
   - `APP_BASE_URL`
3. Start API:
   - `uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000`

## Local Test Commands

- Basic API health:
  - `python3 -m pytest tests/test_api.py::test_health_check -q`
- Auth/entitlement unit checks:
  - `python3 -m pytest tests/test_auth_entitlements.py -q`
