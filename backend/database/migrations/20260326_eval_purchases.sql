-- Migration: Per-evaluation purchases & pending evaluations
-- Replaces subscription-based entitlements with per-eval pricing ($69 first, $29 subsequent)

-- ============================================================
-- 1. eval_purchases — tracks one-time payments for evaluations
-- ============================================================
create table if not exists public.eval_purchases (
  id              uuid        not null default gen_random_uuid(),
  user_id         uuid        references auth.users(id) on delete cascade,  -- NULL until account created
  stripe_payment_intent_id    text,
  stripe_checkout_session_id  text,
  amount_cents    integer     not null,          -- 6900 or 2900
  currency        text        not null default 'usd',
  status          text        not null default 'pending',  -- pending, completed, failed, refunded
  eval_run_id     uuid,                          -- links to prediction_runs.id once finalized
  is_first_eval   boolean     not null default false,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  constraint eval_purchases_pkey primary key (id)
);

create index if not exists idx_eval_purchases_user_id
  on public.eval_purchases(user_id);
create index if not exists idx_eval_purchases_stripe_session
  on public.eval_purchases(stripe_checkout_session_id);

-- RLS
alter table public.eval_purchases enable row level security;

create policy "Users can read own purchases"
  on public.eval_purchases for select
  using (auth.uid() = user_id);

create policy "Service role can manage purchases"
  on public.eval_purchases for all
  using (true)
  with check (true);

-- ============================================================
-- 2. pending_evaluations — holds pre-payment eval data
-- ============================================================
create table if not exists public.pending_evaluations (
  id              uuid        not null default gen_random_uuid(),
  session_token   text        not null unique,
  user_id         uuid,                          -- NULL until account created
  baseball_metrics jsonb      not null,
  ml_prediction   jsonb       not null,
  academic_input  jsonb       not null,
  preferences     jsonb       not null,
  preview_results jsonb       not null,          -- schools, academic/baseball scores (no LLM)
  created_at      timestamptz not null default now(),
  expires_at      timestamptz not null default (now() + interval '24 hours'),
  constraint pending_evaluations_pkey primary key (id)
);

create index if not exists idx_pending_eval_session
  on public.pending_evaluations(session_token);
create index if not exists idx_pending_eval_user
  on public.pending_evaluations(user_id);

-- RLS — service role only (anonymous users can't query directly)
alter table public.pending_evaluations enable row level security;

create policy "Service role can manage pending evaluations"
  on public.pending_evaluations for all
  using (true)
  with check (true);

-- ============================================================
-- 3. Add purchase_id to prediction_runs
-- ============================================================
alter table public.prediction_runs
  add column if not exists purchase_id uuid references public.eval_purchases(id);
