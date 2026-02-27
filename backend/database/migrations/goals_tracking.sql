-- Goals Tracking schema
-- Run in Supabase SQL editor or via migration tooling.

create extension if not exists pgcrypto;

-- ============================================================
-- player_goals: user goal sets with cached sensitivity
-- ============================================================
create table if not exists public.player_goals (
  id uuid default gen_random_uuid() primary key,
  user_id uuid not null references public.profiles(id) on delete cascade,
  position_track text not null check (position_track in ('pitcher', 'infielder', 'outfielder', 'catcher')),
  target_level text not null default 'D1' check (target_level in ('D1', 'Power 4 D1')),
  current_stats jsonb not null,
  target_stats jsonb,
  sensitivity_results jsonb,
  sensitivity_computed_at timestamptz,
  identity_fields jsonb not null default '{}'::jsonb,
  is_active boolean default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_player_goals_user_id on public.player_goals(user_id);

-- ============================================================
-- stat_progress_entries: logged stat updates over time
-- ============================================================
create table if not exists public.stat_progress_entries (
  id uuid default gen_random_uuid() primary key,
  goal_id uuid not null references public.player_goals(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  stat_name text not null,
  stat_value float not null,
  source text default 'manual' check (source in ('manual', 'evaluation', 'verified')),
  evaluation_run_id uuid references public.prediction_runs(id) on delete set null,
  recorded_at timestamptz not null default now()
);

create index if not exists idx_stat_progress_goal on public.stat_progress_entries(goal_id, recorded_at desc);

-- ============================================================
-- position_stat_ranges: reference data (not user-specific)
-- ============================================================
create table if not exists public.position_stat_ranges (
  id uuid default gen_random_uuid() primary key,
  position_track text not null,
  level text not null,
  stat_name text not null,
  p10 float,
  p25 float,
  median float,
  p75 float,
  p90 float,
  mean float,
  std_dev float,
  sample_count int,
  data_version text,
  computed_at timestamptz not null default now(),
  unique (position_track, level, stat_name, data_version)
);

-- ============================================================
-- Triggers
-- ============================================================
drop trigger if exists player_goals_set_updated_at on public.player_goals;
create trigger player_goals_set_updated_at
before update on public.player_goals
for each row execute function public.set_updated_at();

-- ============================================================
-- RLS Policies
-- ============================================================
alter table public.player_goals enable row level security;
alter table public.stat_progress_entries enable row level security;
alter table public.position_stat_ranges enable row level security;

-- player_goals: users manage own
drop policy if exists "player_goals_select_own" on public.player_goals;
create policy "player_goals_select_own" on public.player_goals
  for select to authenticated using (auth.uid() = user_id);

drop policy if exists "player_goals_insert_own" on public.player_goals;
create policy "player_goals_insert_own" on public.player_goals
  for insert to authenticated with check (auth.uid() = user_id);

drop policy if exists "player_goals_update_own" on public.player_goals;
create policy "player_goals_update_own" on public.player_goals
  for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "player_goals_delete_own" on public.player_goals;
create policy "player_goals_delete_own" on public.player_goals
  for delete to authenticated using (auth.uid() = user_id);

-- stat_progress_entries: users manage own
drop policy if exists "stat_progress_select_own" on public.stat_progress_entries;
create policy "stat_progress_select_own" on public.stat_progress_entries
  for select to authenticated using (auth.uid() = user_id);

drop policy if exists "stat_progress_insert_own" on public.stat_progress_entries;
create policy "stat_progress_insert_own" on public.stat_progress_entries
  for insert to authenticated with check (auth.uid() = user_id);

-- position_stat_ranges: all authenticated users can read (reference data)
drop policy if exists "stat_ranges_select_all" on public.position_stat_ranges;
create policy "stat_ranges_select_all" on public.position_stat_ranges
  for select to authenticated using (true);
