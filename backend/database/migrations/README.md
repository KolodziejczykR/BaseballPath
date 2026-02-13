# Database Migrations (Auth + Billing + Persistence)

## New Migration

- `20260211_auth_and_entitlements.sql`

Creates:
- `profiles`
- `subscriptions`
- `prediction_runs`
- `plan_usage_monthly`

Also adds:
- trigger to create `profiles` row for new `auth.users`
- updated-at triggers
- RLS policies for user-scoped access

## How To Run

1. Open Supabase SQL editor.
2. Run SQL from:
   - `backend/database/migrations/20260211_auth_and_entitlements.sql`
3. Confirm tables exist in Supabase table browser.

## Post-Migration Verification

1. Sign up a test user and confirm `profiles` row auto-creates.
2. Run one evaluation and confirm:
   - `prediction_runs` row inserted
   - `plan_usage_monthly` row updated/incremented
3. Query `GET /account/me` and verify plan/usage payload.

