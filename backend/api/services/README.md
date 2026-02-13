# API Services

This directory contains reusable business logic that routers call.

## `plan_service.py`

Responsibilities:
- Ensure profile exists.
- Resolve effective user plan from subscription state.
- Read and increment monthly usage counters.
- Enforce quota limits for evaluations.
- Compute remaining evaluations for UI/API responses.

Core constants:
- `PLAN_STARTER`, `PLAN_PRO`, `PLAN_ELITE`
- `PLAN_EVAL_LIMITS`
- `PLAN_LLM_ENABLED`

Important helper functions:
- `get_effective_plan(user_id)`
- `get_monthly_usage(user_id, period_start=None)`
- `increment_usage(user_id, evaluation_increment=0, llm_increment=0)`
- `enforce_evaluation_quota(user_id, effective_plan)`

For plan/price/tier change instructions, read:
- `PAYMENT_PLANS.md`

