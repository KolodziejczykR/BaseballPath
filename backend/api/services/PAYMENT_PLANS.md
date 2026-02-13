# Payment Plans: How It Works and What To Change

This file documents the current plan system and the exact places to update when pricing or tiers change.

## Current Plan Behavior

Defined in:
- `backend/api/services/plan_service.py`

Current entitlements:
- `starter`
  - 5 evaluations / month
  - LLM reasoning disabled
- `pro`
  - 50 evaluations / month
  - LLM reasoning disabled
- `elite`
  - unlimited evaluations
  - LLM reasoning enabled

Plan fallback:
- If user has no subscription row, plan defaults to `starter`.
- If subscription status is not active/trialing/past_due, effective plan falls back to `starter`.

## Stripe Mapping

Defined in:
- `backend/api/routers/billing.py`

`_stripe_price_ids()` maps plan tier to Stripe Price IDs via env vars:
- `STRIPE_PRICE_ID_PRO`
- `STRIPE_PRICE_ID_ELITE`

Webhook-based sync:
- `checkout.session.completed`
- `customer.subscription.updated`
- `customer.subscription.deleted`

The webhook resolves plan tier from Stripe subscription items and updates `subscriptions`.

## Database Tables Used

Migration:
- `backend/database/migrations/20260211_auth_and_entitlements.sql`

Relevant tables:
- `subscriptions` (plan tier + Stripe ids + status)
- `plan_usage_monthly` (eval/llm counters)
- `prediction_runs` (persisted evaluation history)

## How To Change Plan Limits (same tiers)

If you only want to change monthly limits or LLM access:

1. Edit `PLAN_EVAL_LIMITS` in:
   - `backend/api/services/plan_service.py`
2. Edit `PLAN_LLM_ENABLED` in:
   - `backend/api/services/plan_service.py`
3. Restart backend.

No DB migration needed for this specific change.

## How To Change Stripe Prices (same tiers)

1. Update Stripe Dashboard prices.
2. Update env vars:
   - `STRIPE_PRICE_ID_PRO`
   - `STRIPE_PRICE_ID_ELITE`
3. Restart backend.

No code change needed unless tier names change.

## How To Change Frontend Plan Labels/Amounts

Edit cards in:
- `frontend/src/app/plans/page.tsx`

Adjust:
- displayed `name`
- displayed `price`
- displayed feature bullets
- plan `key` values (must stay aligned with backend tier names unless you update backend too)

## How To Add a New Plan Tier

Example: adding `team`.

You must update all of the following:

1. Backend constants:
   - `backend/api/services/plan_service.py`
   - Add to:
     - `PLAN_*` constants
     - `VALID_PLAN_TIERS`
     - `PLAN_EVAL_LIMITS`
     - `PLAN_LLM_ENABLED`

2. Billing router:
   - `backend/api/routers/billing.py`
   - Add Stripe price mapping in `_stripe_price_ids()`.
   - Ensure checkout validation accepts new tier.

3. DB constraints:
   - `subscriptions.plan_tier` check constraint currently allows only `starter|pro|elite`.
   - Add a migration altering the check constraint to include the new tier.

4. Frontend plans UI:
   - `frontend/src/app/plans/page.tsx`
   - Add card with matching `key` (`team`).

5. Any reporting/dashboard logic expecting only 3 tiers.

## How To Remove or Rename a Tier

1. Update backend constants and billing mappings.
2. Add DB migration:
   - Migrate existing `subscriptions.plan_tier` values.
   - Update check constraint.
3. Update frontend plan keys/cards.
4. Update Stripe price env vars.
5. Test checkout + webhook for renamed tier.

## Local Verification Checklist After Plan Changes

1. `POST /billing/create-checkout-session` returns checkout URL for each paid tier.
2. Complete checkout in Stripe test mode.
3. Send or receive webhook to `/billing/webhook`.
4. Verify `subscriptions.plan_tier` updated.
5. Call `GET /account/me` and confirm:
   - `plan.tier`
   - `plan.monthly_eval_limit`
   - `plan.llm_enabled`
6. Run evaluations to verify quota behavior (`429` when expected).

