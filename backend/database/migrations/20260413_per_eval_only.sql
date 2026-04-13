-- Migration: Per-eval-only billing cutover
-- Drops plan-tier subscription remnants and tightens eval_purchases.user_id.
--
-- Prerequisites (run manually before applying this migration):
--   delete from public.eval_purchases where user_id is null;
--   delete from public.pending_evaluations where expires_at < now();
--
-- After this migration, the only billing model is per-evaluation one-time
-- payments. Auth is required before any paid evaluation, so eval_purchases
-- always has a user_id.

-- ============================================================
-- 1. Drop plan-tier tables (no live users; free to delete)
-- ============================================================
drop table if exists public.plan_usage_monthly cascade;
drop table if exists public.subscriptions cascade;

-- ============================================================
-- 2. Enforce eval_purchases.user_id NOT NULL
-- ============================================================
alter table public.eval_purchases
  alter column user_id set not null;

-- ============================================================
-- 3. Tighten RLS for eval_purchases (service role keeps write access;
--    drop the permissive "all" policy so user inserts must route through
--    the backend, which attaches user_id from the authenticated session).
-- ============================================================
drop policy if exists "Service role can manage purchases" on public.eval_purchases;

create policy "eval_purchases_service_manage"
  on public.eval_purchases for all
  to service_role
  using (true)
  with check (true);
