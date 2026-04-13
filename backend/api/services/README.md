# API Services

This directory contains reusable business logic that routers call.

## `profile_service.py`

Profile row helpers for `public.profiles`.

- `ensure_profile_exists(user_id, email=None)`
- `get_profile(user_id, email=None)` — alias used by routers
- `update_profile(user_id, updates)`

## `evaluation_service.py`

Orchestration for the preview → finalize evaluation pipeline.

- `run_preview_core(...)` — academic + baseball scoring + school matching
- `build_teaser(core)` — 3 randomly-selected schools from the top 10 for the
  unpaid teaser card
- `store_pending_evaluation(...)` — inserts into `pending_evaluations`
- `finalize_paid_evaluation(user_id, session_token, purchase_id)` — verifies
  purchase, re-runs matching over the consideration pool, persists a
  `prediction_runs` row
- `list_runs` / `get_run` / `delete_run` / `delete_all_runs` — per-user CRUD
- `get_public_result(...)` — token-gated public poll for the results page

## `llm_insight_service.py`

Wraps the synchronous summary LLM call and the Celery deep-research enqueue.

- `apply_basic_school_insights(...)`
- `enqueue_deep_school_research(...)`

## `pricing_service.py`

First-eval vs. subsequent-eval price lookup.
