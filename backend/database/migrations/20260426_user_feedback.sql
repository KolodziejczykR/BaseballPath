-- Per-school thumbs feedback and per-run survey feedback.

create extension if not exists pgcrypto;

-- Per-school thumbs up/down with optional reason.
create table if not exists public.school_feedback (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  evaluation_run_id uuid not null references public.prediction_runs(id) on delete cascade,
  school_dedupe_key text not null,
  school_name text not null,
  is_good_fit boolean not null,
  reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, evaluation_run_id, school_dedupe_key)
);

create index if not exists idx_school_feedback_user
  on public.school_feedback(user_id, created_at desc);

create index if not exists idx_school_feedback_run
  on public.school_feedback(evaluation_run_id);

drop trigger if exists school_feedback_set_updated_at on public.school_feedback;
create trigger school_feedback_set_updated_at
before update on public.school_feedback
for each row execute function public.set_updated_at();

alter table public.school_feedback enable row level security;

drop policy if exists "school_feedback_select_own" on public.school_feedback;
create policy "school_feedback_select_own"
on public.school_feedback
for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists "school_feedback_insert_own" on public.school_feedback;
create policy "school_feedback_insert_own"
on public.school_feedback
for insert
to authenticated
with check (auth.uid() = user_id);

drop policy if exists "school_feedback_update_own" on public.school_feedback;
create policy "school_feedback_update_own"
on public.school_feedback
for update
to authenticated
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

drop policy if exists "school_feedback_delete_own" on public.school_feedback;
create policy "school_feedback_delete_own"
on public.school_feedback
for delete
to authenticated
using (auth.uid() = user_id);


-- Per-run survey feedback (one row per user+run).
create table if not exists public.evaluation_feedback (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  evaluation_run_id uuid not null references public.prediction_runs(id) on delete cascade,
  level_rating text check (level_rating in ('too_low', 'just_right', 'too_high')),
  match_quality smallint check (match_quality between 1 and 5),
  discovery text check (discovery in ('yes', 'some', 'no')),
  improvement text,
  praise text,
  quote_consent boolean not null default false,
  display_name text,
  dismissed boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, evaluation_run_id)
);

create index if not exists idx_evaluation_feedback_user
  on public.evaluation_feedback(user_id, created_at desc);

drop trigger if exists evaluation_feedback_set_updated_at on public.evaluation_feedback;
create trigger evaluation_feedback_set_updated_at
before update on public.evaluation_feedback
for each row execute function public.set_updated_at();

alter table public.evaluation_feedback enable row level security;

drop policy if exists "evaluation_feedback_select_own" on public.evaluation_feedback;
create policy "evaluation_feedback_select_own"
on public.evaluation_feedback
for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists "evaluation_feedback_insert_own" on public.evaluation_feedback;
create policy "evaluation_feedback_insert_own"
on public.evaluation_feedback
for insert
to authenticated
with check (auth.uid() = user_id);

drop policy if exists "evaluation_feedback_update_own" on public.evaluation_feedback;
create policy "evaluation_feedback_update_own"
on public.evaluation_feedback
for update
to authenticated
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

drop policy if exists "evaluation_feedback_delete_own" on public.evaluation_feedback;
create policy "evaluation_feedback_delete_own"
on public.evaluation_feedback
for delete
to authenticated
using (auth.uid() = user_id);
