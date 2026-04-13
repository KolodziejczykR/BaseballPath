# Backend API Guide

Production auth, billing, and persisted evaluation orchestration for
BaseballPath.

## Directory Layout

- `routers/`: FastAPI route handlers grouped by domain.
- `deps/`: shared FastAPI dependencies (auth).
- `services/`: business logic helpers (profile, evaluation pipeline, LLM,
  pricing, sensitivity). Pure Python — no FastAPI imports.
- `clients/`: external client setup helpers (Supabase admin client).
- `main.py`: primary FastAPI app entrypoint.
- `main_waitlist.py`: waitlist-only app entrypoint.

## What Was Implemented

### Auth + Account

- Protected token verification dependency: `deps/auth.py`
  (`get_current_user` is required, `get_optional_user` allows anonymous
  callers to pass through).
- Account endpoints:
  - `GET /account/me`
  - `PATCH /account/me`
- Router: `routers/account.py`.

### Evaluations (preview → finalize)

Router: `routers/evaluations.py` is a thin HTTP layer over
`services/evaluation_service.py`. Funnel: survey → preview → signup/login →
Stripe checkout → finalize → results.

- `POST /evaluations/preview` — anonymous. Runs academic + baseball scoring
  and school matching, stores a `pending_evaluations` row, and returns a
  session token plus 3 randomly-selected teaser schools from the top 10.
  Authenticated callers also get pricing for their next evaluation.
- `POST /evaluations/finalize` — **auth required**. Verifies the Stripe
  purchase, re-runs matching across the consideration pool, persists a
  `prediction_runs` row with `user_id + purchase_id`, and enqueues deep
  roster research on Celery.
- `GET /evaluations/result` — token-gated public poll used by the results
  page while the Celery job is still writing deep insights.
- `GET /evaluations` — authenticated list of the caller's runs.
- `GET /evaluations/{run_id}` — authenticated single run.
- `DELETE /evaluations/{run_id}` — authenticated delete.
- `DELETE /evaluations?confirm=true` — authenticated bulk delete.

### Billing (per-evaluation one-time payments)

Router: `routers/billing.py`. Per-eval Stripe one-time payments are the only
billing model; the plan-tier/subscription path was deleted in the
`20260413_per_eval_only.sql` migration.

- `POST /billing/create-eval-checkout` — **auth required**. Creates a
  Stripe Checkout Session in `mode=payment` (price computed at session time
  via `services/pricing_service.py`) and writes a `pending` row into
  `eval_purchases` with `user_id` set.
- `POST /billing/webhook` — handles `checkout.session.completed` events
  with `metadata.payment_type == "eval_purchase"` and flips the matching
  `eval_purchases` row to `completed`.

### Waitlist

- Router: `routers/waitlist.py`
- Endpoints: `POST /waitlist/join`, `GET /waitlist/health`

Frontend stays on `/prelaunch` and shows success inline after
`POST /waitlist/join`.

## Services

- `services/profile_service.py` — `ensure_profile_exists`, `get_profile`,
  `update_profile`.
- `services/evaluation_service.py` — `run_preview_core`, `build_teaser`,
  `store_pending_evaluation`, `finalize_paid_evaluation`, `get_public_result`,
  and per-user CRUD for `prediction_runs`.
- `services/llm_insight_service.py` — synchronous summary LLM call plus
  `enqueue_deep_school_research` (Celery hand-off).
- `services/pricing_service.py` — first-eval vs. repeat-eval price lookup.
- `services/sensitivity_service.py` — what-if sensitivity analysis.

## How it Works End-to-End

1. Frontend submits the survey to `POST /evaluations/preview`. Backend runs
   the full evaluation, stores a `pending_evaluations` row keyed by a new
   session token, and returns 3 teaser schools + the token.
2. Frontend renders the 3 teaser schools. Anonymous users are routed to
   signup/login with the session token attached.
3. After auth, the frontend posts to `POST /billing/create-eval-checkout`
   with the session token. Backend creates a Stripe Checkout Session and
   writes an `eval_purchases` row with `user_id` + `status=pending`.
4. User completes Stripe checkout. The webhook flips the `eval_purchases`
   row to `completed`.
5. Frontend posts to `POST /evaluations/finalize` with the session token
   and the purchase id. Backend re-runs matching over the consideration
   pool, writes a `prediction_runs` row with `user_id + purchase_id`, and
   enqueues a Celery job for deep roster research.
6. Frontend redirects to `/evaluations/{run_id}`, which polls the run row
   until the Celery job finishes populating deep insights.

## Local Setup Checklist

1. Apply migrations in order:
   - `backend/database/migrations/20260211_auth_and_entitlements.sql`
   - `backend/database/migrations/20260327_prediction_runs_add_catcher.sql`
   - `backend/database/migrations/20260413_per_eval_only.sql`
     (prereq cleanup: `delete from public.eval_purchases where user_id is null;`
     and `delete from public.pending_evaluations where expires_at < now();`)
2. Set backend env vars:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`
   - `SUPABASE_ANON_KEY`
   - `SUPABASE_JWT_ISSUER` (optional)
   - `SUPABASE_JWT_AUDIENCE` (optional, defaults to `authenticated`)
   - `STRIPE_SECRET_KEY`
   - `STRIPE_WEBHOOK_SECRET`
   - `APP_BASE_URL` (used to build Stripe success/cancel URLs)
   - `OPENAI_API_KEY` (optional — if unset, deep research is skipped)
3. Start API:
   - `uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000`
4. Start the Celery worker + Redis if you want deep roster research to run.

## Local Test Commands

- Auth gating checks:
  `python3 -m pytest tests/test_auth_entitlements.py -q`
- Evaluation service unit tests:
  `python3 -m pytest tests/testbackend/test_evaluation_service.py -q`
- LLM insight service unit tests:
  `python3 -m pytest tests/testbackend/test_llm_insight_service.py -q`
- Evaluation route integration tests:
  `python3 -m pytest tests/test_evaluation_routes.py -q`
- Full backend suite:
  `python3 -m pytest tests/ -q`
