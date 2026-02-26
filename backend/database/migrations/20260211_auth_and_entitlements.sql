-- Auth, billing, and evaluation persistence schema.
-- Run in Supabase SQL editor or via migration tooling.

create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text,
  state text,
  grad_year int,
  primary_position text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.subscriptions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  plan_tier text not null check (plan_tier in ('starter', 'pro', 'elite')),
  status text not null check (status in ('active', 'trialing', 'past_due', 'canceled', 'incomplete', 'none', 'unknown')),
  stripe_customer_id text unique,
  stripe_subscription_id text unique,
  current_period_start timestamptz,
  current_period_end timestamptz,
  cancel_at_period_end boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(user_id)
);

create table if not exists public.prediction_runs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  created_at timestamptz not null default now(),
  position_track text not null check (position_track in ('pitcher', 'infielder', 'outfielder')),
  identity_input jsonb not null,
  stats_input jsonb not null,
  preferences_input jsonb not null,
  prediction_response jsonb not null,
  preferences_response jsonb not null,
  top_schools_snapshot jsonb,
  llm_reasoning_status text,
  llm_job_id text
);

create table if not exists public.plan_usage_monthly (
  user_id uuid not null references public.profiles(id) on delete cascade,
  period_start date not null,
  eval_count int not null default 0 check (eval_count >= 0),
  llm_count int not null default 0 check (llm_count >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (user_id, period_start)
);

create index if not exists idx_prediction_runs_user_created_at
  on public.prediction_runs(user_id, created_at desc);

create index if not exists idx_subscriptions_user_id
  on public.subscriptions(user_id);

create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists profiles_set_updated_at on public.profiles;
create trigger profiles_set_updated_at
before update on public.profiles
for each row execute function public.set_updated_at();

drop trigger if exists subscriptions_set_updated_at on public.subscriptions;
create trigger subscriptions_set_updated_at
before update on public.subscriptions
for each row execute function public.set_updated_at();

drop trigger if exists plan_usage_monthly_set_updated_at on public.plan_usage_monthly;
create trigger plan_usage_monthly_set_updated_at
before update on public.plan_usage_monthly
for each row execute function public.set_updated_at();

create or replace function public.create_profile_for_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, full_name)
  values (
    new.id,
    coalesce(new.raw_user_meta_data ->> 'full_name', split_part(new.email, '@', 1))
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute function public.create_profile_for_new_auth_user();

alter table public.profiles enable row level security;
alter table public.subscriptions enable row level security;
alter table public.prediction_runs enable row level security;
alter table public.plan_usage_monthly enable row level security;

drop policy if exists "profiles_select_own" on public.profiles;
create policy "profiles_select_own"
on public.profiles
for select
to authenticated
using (auth.uid() = id);

drop policy if exists "profiles_update_own" on public.profiles;
create policy "profiles_update_own"
on public.profiles
for update
to authenticated
using (auth.uid() = id)
with check (auth.uid() = id);

drop policy if exists "subscriptions_select_own" on public.subscriptions;
create policy "subscriptions_select_own"
on public.subscriptions
for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists "prediction_runs_select_own" on public.prediction_runs;
create policy "prediction_runs_select_own"
on public.prediction_runs
for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists "prediction_runs_insert_own" on public.prediction_runs;
create policy "prediction_runs_insert_own"
on public.prediction_runs
for insert
to authenticated
with check (auth.uid() = user_id);

drop policy if exists "plan_usage_monthly_select_own" on public.plan_usage_monthly;
create policy "plan_usage_monthly_select_own"
on public.plan_usage_monthly
for select
to authenticated
using (auth.uid() = user_id);

